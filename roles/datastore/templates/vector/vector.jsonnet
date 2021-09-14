local tpl(str) = std.native('ansible_expr')(str);

// base

local Component(name) = {
  name: name,
};

// pipelines

local Pipeline = {
  sources: [],
  transforms: [],
  sinks: [],
};

local File(name, files, script=null) = Pipeline {
  assert std.isArray(files),

  p01:: (if script != null then 'final_' else 'sink_') + name + '_files',

  sources: [
    Component('source_files_' + name) {
      type: 'file',
      ignore_older_secs: 800,
      read_from: 'beginning',
      include: files,
      encoding: { charset: 'UTF-8' },
    },
  ],
  transforms: [
    Component($.p01) {
      type: 'remap',
      inputs: ['source_files_' + name],
      source: '\n.vector_type = "file"\n.category = "' + name + '"',
    },
    if script != null then Component('sink_' + name + '_files') {
      type: 'remap',
      inputs: [$.p01],
      file: tpl('{{ vector_scripts_dir }}/' + script),
    },
  ],
};

// sinks

local loki_sink = Component('loki_sink') {
  type: 'loki',
  inputs: ['absolute_sink_*'],
  endpoint: tpl('{{ loki_endpoint }}'),
  // remove_label_fields: true,
  out_of_order_action: 'rewrite_timestamp',
  // out_of_order_action: 'drop',


  labels: {
    forwarder: 'vector',
    host: '{{ host }}',
    level: '{{ level }}',
    vector_type: '{{ vector_type }}',
    category: '{{ category }}',
    application: '{{ application }}',
  },

  encoding: {
    codec: 'json',
    timestamp_format: 'rfc3339',
  },

  /*
    buffer: {
      type: 'disk',
      // type: 'memory',
      // max_events: 0,

      when_full: 'block',
      max_size: 80000000000,
      // when_full: 'drop_newest',
    },
  */

  request: {
    concurrency: 'adaptive',
    // concurrency: 2,
    // retry_max_duration_secs: 120,
    // timeout_secs: 30,
    // in_flight_limit: 1,
  },
};

local influxdb_sink = Component('influxdb_sink') {
  type: 'influxdb_logs',
  inputs: ['absolute_sink_*'],
  bucket: 'logs',
  database: tpl('{{ vector_influxdb_database_name }}'),
  endpoint: 'http://influxdb:8086/',
  retention_policy_name: 'autogen',
  namespace: 'service',

  encoding: {
    timestamp_format: 'rfc3339',
  },
};

local file_sink = Component('file_sink') {
  type: 'file',
  inputs: ['absolute_sink_*'],
  idle_timeout_secs: 30,
  compression: 'none',
  path: '/tmp/vector-%Y-%m-%d.log',

  encoding: {
    codec: 'ndjson',
    timestamp_format: 'rfc3339',
  },
};

local socket_sink = Component('socket_sink') {
  type: 'socket',
  inputs: ['absolute_sink_*'],
  address: tpl('fluent-bit:{{ fluent_bit_tcp_input_port }}'),
  mode: 'tcp',

  encoding: {
    codec: 'json',
    timestamp_format: 'rfc3339',
  },

  buffer: {
    type: 'disk',
    // type: 'memory',
    // max_events: 0,

    when_full: 'block',
    max_size: 80000000000,
    // when_full: 'drop_newest',
  },
};

local elasticsearch_sink = Component('elasticsearch_sink') {
  type: 'elasticsearch',
  inputs: ['absolute_sink_*'],
  bulk_action: 'create',
  //doc_type: "_doc",
  endpoint: 'http://elasticsearch:9200',
  //id_key: "id",
  index: 'vector-%F',
  mode: 'data_stream',
  //pipeline: "pipeline-name",
  compression: 'none',

  encoding: {
    codec: 'default',
    timestamp_format: 'rfc3339',
    except_fields: ['host'],
  },
};

// transforms

local sanity_corrections = Component('absolute_sink_sanity_corrections') {
  type: 'remap',
  inputs: ['except_traefik', 'geo_ip'],
  file: tpl('{{ vector_scripts_dir }}/ensure_sanity.vrl'),
};

local pipelines = [
  Pipeline {
    sources: [
      Component('source_syslog_stream') {
        type: 'syslog',
        address: tpl('0.0.0.0:{{ vector_syslog_port }}'),
        max_length: 102400,
        mode: 'udp',
        path: tpl('{{ vector_volumes_data.mount }}/syslog.socket'),
        host_key: tpl('{{ host_name }}'),
      },
    ],
    transforms: [
      Component('sink_syslog_stream_remap_labels') {
        type: 'remap',
        inputs: ['source_syslog_stream'],
        file: tpl('{{ vector_scripts_dir }}/syslog_stream.vrl'),
      },
    ],
  },
  File('dmesg', [tpl('{{ vector_log_path }}/dmesg')]),
  File('docker_logs', ['/var/lib/docker/containers/**/*.log'], 'docker.vrl') {
    transforms+: [
      Component('only_traefik') {
        type: 'filter',
        inputs: ['sink_*'],
        condition: '.application == "traefik"',
      },

      Component('except_traefik') {
        type: 'filter',
        inputs: ['sink_*'],
        condition: '.application != "traefik"',
      },

      Component('geo_ip') {
        type: 'geoip',
        inputs: ['only_traefik'],
        database: tpl('{{ maxmind_volumes_data.mount }}/GeoLite2-City.mmdb'),
        source: 'data.ClientHost',
        target: 'geoip',
      },
    ],
  },
  Pipeline {
    transforms: [
      Component('geo_ip_to_metric') {
        metric:: function(name) {
          field: 'geoip',
          name: name + '_total',
          namespace: 'geoip',
          type: 'counter',

          labels: {
            [name]: '{{ ' + name + ' }}',
          },
        },

        type: 'log_to_metric',
        inputs: ['geo_ip'],

        metrics: [
          self.metric('city_name'),
          self.metric('continent_code'),
          self.metric('country_code'),
          self.metric('latitude'),
          self.metric('longitude'),
          self.metric('post_code'),
          self.metric('timezone'),
        ],
      },
    ],
    sinks: [
      Component('prometheus_sink') {
        type: 'prometheus_exporter',
        inputs: ['geo_ip_to_metric'],
        address: '0.0.0.0:9898',
        default_namespace: 'service',
      },
    ],
  },
];

//
// Components
//

local make(arr) = std.prune(std.flattenArrays(arr));

local sinks_ = make([
  [socket_sink],
  std.flattenArrays([x.sinks for x in pipelines]),
]);

local transforms_ = make([
  [sanity_corrections],
  std.flattenArrays([x.transforms for x in pipelines]),
]);

local sources_ = make([x.sources for x in pipelines]);

//
// Output JSON
//

local Output(obj) = {
  [k]: obj[k]
  for k in std.objectFieldsAll(obj)
  if k != 'name'
};

{
  data_dir: tpl('{{ vector_volumes_data.mount }}'),

  healthchecks: {
    enabled: true,
  },

  // Vector's API (disabled by default)
  // Enable and try it out with the `vector top` command
  api: {
    enabled: true,
    address: tpl('0.0.0.0:{{ vector_api_port }}'),
    playground: true,
  },

  sinks: {
    [sink.name]: Output(sink)
    for sink in sinks_
  },

  transforms: {
    [transform.name]: Output(transform)
    for transform in transforms_
  },

  sources: {
    [source.name]: Output(source)
    for source in sources_
  },
}
