# -*- mode: ruby -*-
# vi: set ft=ruby :

def setup_disk(v, name, num)
  unless File.exist?(name)
    v.customize ['createhd', '--filename', name,'--format', 'VDI', '--size', 10 * 1024]
  end
  v.customize ['storageattach', :id, '--storagectl', 'SCSI', '--port', num + 2, '--device', 0, '--type', 'hdd', '--medium', name]
end

Vagrant.configure("2") do |config|
  # config.vm.box = "debian/buster64"
  config.vm.box = "ubuntu/focal64"
  config.vm.hostname = "realmar-dev"
  # config.vm.network "public_network", :mac => "080027370D99"
  config.vm.network "private_network", ip: "192.168.250.102"
  config.vm.synced_folder ".", "/vagrant", disabled: true
  config.disksize.size = '100GB'

  config.vm.provider "virtualbox" do |v|
    v.memory = 16384
    v.cpus = 12

    setup_disk(v, './sdb.vdi', 0)
    setup_disk(v, './sdc.vdi', 1)
    # setup_disk(v, './sdd.vdi', 2)
    # setup_disk(v, './sde.vdi', 3)
    # setup_disk(v, './sdf.vdi', 4)
    # setup_disk(v, './sdg.vdi', 5)
    # setup_disk(v, './sdh.vdi', 6)
    # setup_disk(v, './sdi.vdi', 7)
    # setup_disk(v, './sdj.vdi', 8)
    # setup_disk(v, './sdk.vdi', 9)
    # setup_disk(v, './sdl.vdi', 10)
    # setup_disk(v, './sdm.vdi', 11)
    # setup_disk(v, './sdn.vdi', 12)
  end

  config.vm.provision "shell" do |s|
    ssh_pub_key = File.readlines("#{Dir.home}/.ssh/id_ed25519.pub").first.strip
    nopass_ssh_pub_key = File.readlines("#{Dir.home}/.ssh/id_rsa_nopassphrase.pub").first.strip
    authorized_keys = "/root/.ssh/authorized_keys"

    s.inline = <<-SHELL
      apt-get update
      apt-get install -y python3 python3-pip

      mkdir -p /root/.ssh
      chmod 700 /root/.ssh

      echo #{ssh_pub_key} > #{authorized_keys}
      echo "\n" >> #{authorized_keys}
      echo #{nopass_ssh_pub_key} >> #{authorized_keys}
      echo "\n" >> #{authorized_keys}

      chmod 600 #{authorized_keys}
    SHELL
  end
end
