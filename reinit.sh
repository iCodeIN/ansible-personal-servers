ssh-keygen -f "/home/realmar/.ssh/known_hosts" -R "192.168.250.101"
ssh-keygen -f "/home/realmar/.ssh/known_hosts" -R "192.168.250.102"
ssh-keygen -f "/home/realmar/.ssh/known_hosts" -R "192.168.250.103"
ssh-keygen -f "/home/realmar/.ssh/known_hosts" -R "192.168.250.104"

ssh -o "ForwardAgent yes" -o "ForwardX11 yes" -o "StrictHostKeyChecking accept-new" root@192.168.250.101 "touch ~/.Xauthority && xauth add :0 . `mcookie` && exit"
ssh -o "ForwardAgent yes" -o "ForwardX11 yes" -o "StrictHostKeyChecking accept-new" root@192.168.250.102 "touch ~/.Xauthority && xauth add :0 . `mcookie` && exit"
ssh -o "ForwardAgent yes" -o "ForwardX11 yes" -o "StrictHostKeyChecking accept-new" root@192.168.250.103 "touch ~/.Xauthority && xauth add :0 . `mcookie` && exit"
ssh -o "ForwardAgent yes" -o "ForwardX11 yes" -o "StrictHostKeyChecking accept-new" root@192.168.250.104 "touch ~/.Xauthority && xauth add :0 . `mcookie` && exit"
