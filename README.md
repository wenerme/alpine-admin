# Alpine Admin
Ansible Role for Alpine Host

* Dependencies
  * [wenerme/ansible-collection-wenerme-alpine](https://github.com/wenerme/ansible-collection-wenerme-alpine) - Collection of tasks for operation and maintenance AlpineLinux


```bash
git clone https://github.com/wenerme/alpine-admin
cd alpine-admin
# ansible env
docker run --rm -it \
  -e TZ=Asia/Shanghai \
  -v $HOME/.ansible:/root/.ansible \
  -v $PWD:/host -w /host \
  --name ansible wener/ansible
# install dependencies
ansible-galaxy install -r requirement.yml
```

## 文件结构
* credentials - 保存证书等相关内容
  * admin_rsa.pri - 加密后的私钥 - 控制机器需要 ssh-add
  * admin_rsa.pub - 管理员公钥 - setup-base 时如果存在会拷贝到主机
* files - 配置文件
  * ${service_name} - 服务的配置文件
  * ${hostname} - 针对主机的配置文件
    * ${service_name} - 针对主机的服务配置文件
* cache - 缓存文件 - 不提交仓库
  * facts - 缓存主机的信息
* roles
  * alpine - AlpineLinux 管理运维
  * dev - 开发相关操作
  * docker - 容器应用 - 避免每次都记参数命令

## 准备工作

__安装 Ansible__
```bash
# macOS 安装 ansible 环境
brew install ansible
```

__准备主机列表__

```bash
# 替换为自己的主机
cat <<HOSTS > hosts
host01 ansible_ssh_user=root ansible_ssh_host=192.168.1.2
host02 ansible_ssh_user=root ansible_ssh_host=192.168.1.3
HOSTS
# 设置默认主机列表
cat <<CFG ansible.cfg
[defaults]
inventory=hosts
CFG
```

__生成管理员密钥__

> 💡提示
>
> 以下的操作等同于
>
> ```
> ansible-playbook adhoc.yaml -e 'role=dev task=admin-credentials-gen' -i localhost
> ```


```bash
# 用于生成随机密码
alias random-passwd="cat /dev/urandom | env LC_CTYPE=C tr -dc 'a-zA-Z0-9' | head -c 32"

# 生成密钥
mkdir vault
# 密码位于 admin_rsa.passwd 文件
ssh-keygen -t rsa -N $(random-passwd|tee credentials/admin_rsa.passwd) -f credentials/admin_rsa

# vault 加密 - 加密后可以提交到代码仓库 admin_rsa.pri
random-passwd > credentials/admin_rsa_vault.passwd
# 加密后的私钥为 admin_rsa.pri
ansible-vault encrypt credentials/admin_rsa --output=credentials/admin_rsa.pri --vault-password-file=credentials/admin_rsa_vault.passwd

# 注意: 不要提交 *.passwd 和 vault/admin_rsa 到仓库
echo -e '*.passwd\n*_rsa' >> .gitignore

# 之后使用时解密然后 ssh-add 即可
# 分别输入 admin_rsa_vault.passwd 和 admin_rsa.passwd 密码
ansible-vault view credentials/admin_rsa.pri | ssh-add -
```

## 常用任务

```bash
# 直接执行单个任务
ansible-playbook adhoc.yaml -e 'task=setup-base'
# 限制执行的主机
# 本地执行 -i localhost
ansible-playbook adhoc.yaml -e 'task=setup-base' -l dev
# 任务携带额外参数
ansible-playbook adhoc.yaml -e 'task=tinc-service tinc_netname=mynet'
```

## 任务说明

### 基础任务
* alpine-update - apk update
* alpine-upgrade - apk upgrade
* wener-repo - 安装 [wenerme/repository](https://github.com/wenerme/repository) 仓库
  * 主要包含没有在官方仓库的一些包 - 例如 tinc-pre
* resizefs - ⚠️ 对 __sda__ 进行分区大小调整
  * 通常用于在调整了磁盘大小后使用
  * 例如 `qemu-img resize disk.qcow2 20G` 修改完磁盘大小然后需要修改分区
* cleanup - 移除 shell 历史和 `~/.ansible` 目录
* ensure-python - 确保安装 python - 在新的主机上安装 ansible 需要的环境

### SETUP

* setup-base - 基础配置
  * 确保 python 环境 - ansible 依赖
  * 安装基础包
  * 设置 admin 帐号
  * 拷贝 admin 公钥 credentials/admin_rsa.pub
  * 允许 admin 无密码 sudo
  * 移除密码登录
  * 禁止 root 远程登录
* setup-base-service - 基础服务配置
  * keymap
  * timezone
  * ntp
  * acpid
  * mdev
* setup-ops - 运维节点配置
  * 安装运维常用的包
* setup-phy - 物理节点配置
  * 安装物理节点常用的包
* setup-virt-node - 设置运行在 libvirt 中的节点
  * 会安装 qemu-agent
  * 启动 acpid - libvirt 的关机基于 acpid 命令

### 服务维护

* ensure-service - 确保服务运行
  * 参数 `service_name` 服务的名字
  * 通过 _service-started_ 检测服务是否运行
  * 通过 `{{service_name}}_service` 启动服务
  * 支持的服务
    * udev
    * nginx
    * docker
    * local

### TINC

* tinc-install - 安装 tinc-pre
* tinc-service - 启动 tincd
  * 参数 `tinc_netname` 需要配置在 `/etc/conf.d/tinc.network` 中的网络名

## 本地实验

基于 docker 创建多个镜像进行本地 ansible 管理

```bash
# 启动容器
ansible-playbook adhoc.yaml -e 'role=dev task=play-container-create facts=true' -i localhost
# 可以考虑映射 $PWDcache/apk:/etc/apk/cache 作为 apk 缓存 - 当容器较多时安装速度更快
# ansible-playbook adhoc.yaml -e '{"role":"dev","task":"play-container-create","facts":true,"play_volumes":["'$PWD'/cache/apk:/etc/apk/cache"]}' -i localhost

# 检测存活
ansible all -i plays -m ping
# 进行操作
ansible-playbook adhoc.yaml -e 'task=setup-base' -i plays

# 实验完成销毁容器
ansible-playbook adhoc.yaml -e 'role=dev task=play-container-destroy' -i localhost

# 本地虚拟机
# ssh 127.0.0.1:2222
ansible all -i localvm -m ping
```

## 技巧

## 设置别名更方便使用
```bash
# 简化执行
# adhoc setup-base -e 'ansible_user=root' -l myhost
adhoc(){ local task=$1; shift; ansible-playbook $PWD/adhoc.yaml -e task=$task $*; }

# 新增节点 - 确定能无密码登陆
ssh-copy-id root@10.0.0.1
# 使用 root 账户初始 - 默认使用 admin
adhoc setup-base -l node-1 -e ansible_user=root

# 初始化帮助运维的工具
adhoc setup-ops -l node-1

# 节点信息概览 - 系统/CPU/内存/网络
adhoc host-info
adhoc resizefs
```

## 使用 Ansible Vault 加密密钥

```bash
# 生成密码
cat /dev/urandom | env LC_CTYPE=C tr -dc 'a-zA-Z0-9' | head -c 32 > credentials/secrets.passwd
# 指定默认密码文件
export ANSIBLE_VAULT_PASSWORD_FILE=$PWD/credentials/secrets.passwd
# 生成密钥文件
touch credentials/secrets.yaml
# 加密密钥文件
ansible-vault encrypt credentials/secrets.yaml

# 编辑添加内容
# 例如 db_password: changeme
ansible-vault edit credentials/secrets.yaml

# 使用密钥文件
ansible-playbook adhoc.yaml -e 'task=setup-base' -l myhost -e @credentials/secrets.yaml
```

## 使用场景

### tinc 网络初始化

```yaml
all:
  hosts:
    # server node
    interos:
      # tinc server node - accessable by other nodes
      ansible_host: 100.100.100.100
      # tinc address of this node
      tinc_address: 10.10.1.1
      tinc_conf:
      # use switch mode
      - {name: Mode, value: Switch}
      tinc_host_conf:
      # default port
      - {name: Port, value: 665}
      # add subnet for this node
      - {name: Subnet, value: "{{tinc_subnet|ipaddr('1')|ipaddr('address')}}/32"}
      # address or domain access by other nodes
      - {name: Address, value: 100.100.100.100}

    node-1:
      ansible_host: 192.168.1.100
      tinc_address: 10.10.1.2

    node-2:
      ansible_host: 192.168.1.101
      tinc_address: 10.10.1.3

  children:
    nodes:
      hosts:
        node-1:
        node-2:
  vars:
    ansible_user: admin
    # use py 3
    ansible_python_interpreter: /usr/bin/python3
    tinc_netname: "interos"
    tinc_subnet: 10.10.0.0/16
    # node default conf - use random port
    tinc_host_conf:
      - {name: Port, value: 0}
```

```bash
# init server
adhoc tinc-init -l interos
adhoc tinc-service -l interos

# join nodes
adhoc tinc-join -l nodes
adhoc tinc-service -l nodes
```

### K3S 部署
* 准备工作
  * 确保网络通，如果混合云，使用 Tinc 打通网络，用 Tinc 作为 flannel backend
  * 配置主机

__示例配置__

```yaml
# 两个分组 k3s-server 和 k3s-worker

all:
  children:
    k3s-server:
      hosts:
        # 主机
        k3s-master-1:
      vars:
        k3s_role: server
        # flannel-iface 使用了 tinc
        # k3s_node_ip 节点 IP - 用了 tinc 则于 tinc 地址相同
        k3s_install_options: >-
          --disable=traefik,servicelb
          --flannel-backend=host-gw
          --docker
          --flannel-iface={{tinc_netname}}
          --node-ip={{k3s_node_ip}}
        k3s_install_env: |
          INSTALL_K3S_EXEC=server
        # k3s_database_url 数据库地址
        k3s_env: |
          K3S_DATASTORE_ENDPOINT={{k3s_database_url}}
          K3S_NODE_NAME={{hostname|default(inventory_hostname)}}

    k3s-worker:
      hosts:
        # 主机
        k3s-worker-1:
      vars:
        k3s_role: agent
        k3s_install_env: |
          INSTALL_K3S_EXEC=agent
        k3s_install_options: >-
          --docker
          --flannel-iface={{tinc_netname}}
          --node-ip={{k3s_node_ip}}
        # k3s_master_ip 主节点地址
        # k3s_node_token 主节点的 token - 部署后才能取到
        k3s_env: |
          NODE_IP={{k3s_node_ip}}
          K3S_URL=https://{{k3s_master_ip}}:6443
          K3S_TOKEN={{k3s_node_token}}
          K3S_NODE_NAME={{hostname|default(inventory_hostname)}}

```

```bash
# 下载到本地
adhoc k3s-download
# 准备 - 内核参数，必要配置，安装必要环境
adhoc k3s-prepare
# 修改了内核参数可能需要重启
adhoc reboot

# 安装 server
adhoc k3s-install -l k3s-server
# 启动
adhoc k3s-service -l k3s-server
# 拉取配置
adhoc k3s-server-conf-pull -l k3s-master-1

# 添加 token 配置

# 安装 worker
adhoc k3s-install -l k3s-worker
# 启动
adhoc k3s-service -l k3s-server
# 完成
```

> 可以针对 server 和 worker 写 playbook 使得部署更简单

### AlpineLinux 本地 DNS 缓存
Alpine 的 DNS 在有时候会非常慢， musl 和 Linux 内核历来就有的问题

```yaml
all:
  hosts:
    node:
      ansible_host: 192.168.1.1
      # can use other address
      resolv_conf: |
        nameserver {{ansible_host}}
  vars:
    ansible_user: admin
    ansible_python_interpreter: /usr/bin/python3
    # upstream dns
    dnsmasq_resolv_conf: |
      nameserver 223.5.5.5
      nameserver 114.114.114.114
```

```bash
# start dnsmasq
adhoc dnsmasq-service
# disable udhcpc override resolv.conf
adhoc udhcpc-resolv-conf-no
# config resolv.conf
adhoc resolv-conf-sync
```

# FAQ
## 不克隆仓库本地同步使用这里的 roles

```bash
SRC=$PWD
DEST=other/project
rsync -a $SRC/roles/{alpine,dev} $DEST/roles/
# 拷贝 plays
rsync -a $SRC/roles/alpine/plays/ $DEST/
```
