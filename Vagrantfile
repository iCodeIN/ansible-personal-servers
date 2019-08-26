# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure("2") do |config| 
  config.vm.box = "generic/ubuntu1804"
  config.vm.hostname = "pihole-dev"

  config.vm.provision "shell" do |s|
    ssh_pub_key = File.readlines("#{Dir.home}/.ssh/id_rsa.pub").first.strip
    s.inline = <<-SHELL
      apt-get update
      apt-get install -y python

      mkdir -p /root/.ssh
      chmod 700 /root/.ssh

      echo #{ssh_pub_key} >> /root/.ssh/authorized_keys

      chmod 600 /root/.ssh/authorized_keys
    SHELL
  end
end
