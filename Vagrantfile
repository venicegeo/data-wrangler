# -*- mode: ruby -*-
# vi: set ft=ruby :

VAGRANTFILE_API_VERSION = "2"

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|

	config.vm.define "dw" do |dw|
		dw.vm.box = "geerlingguy/centos7"
		dw.vm.hostname = "dw.dev"
		dw.vm.provision :shell, path: "dw-bootstrap.sh"
		dw.vm.network :private_network, ip:"192.168.20.20"
		dw.vm.network "forwarded_port", guest: 8080, host: 8081
		dw.vm.network "forwarded_port", guest: 27017, host: 27017
		dw.vm.network "forwarded_port", guest: 5432, host: 5432
		dw.vm.synced_folder "./", "/vagrant"
		dw.vm.provider "virtualbox" do |vb|
		  vb.customize ["modifyvm", :id, "--memory", "512"]
		end
	end

end