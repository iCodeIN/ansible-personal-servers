CREATE DATABASE {{ matrix_server_db_name }}
  ENCODING 'UTF8'
  LC_COLLATE='C'
  LC_CTYPE='C'
  template=template0
  OWNER {{ matrix_server_db_user }};

{% for name in [
  matrix_server_db_telegram_name,
  matrix_server_db_whatsapp_name,
  matrix_server_db_signal_name,
  matrix_server_db_instagram_name,
  matrix_server_db_twitter_name ] %}
CREATE DATABASE {{ name }}
  OWNER {{ matrix_server_db_user }};
{% endfor %}
