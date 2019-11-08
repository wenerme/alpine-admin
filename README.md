# Alpine Admin
Ansible Role for Alpine Host

## 文件结构
* vault - 保存密钥相关内容
  * admin_rsa.pri - 加密后的私钥 - 控制机器需要 ssh-add
  * admin_rsa.pub - 管理员公钥 - setup-base 时如果存在会拷贝到主机
* files - 过程文件

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
  * 拷贝 admin 公钥 vault/admin_rsa.pub
  * 允许 admin 无密码 sudo
  * 移除密码登录
  * 禁止 root 远程登录
* setup-virt-node - 设置运行在 libvirt 中的节点
  * 会安装 qemu-agent
  * 启动 acpid - libvirt 的关机基于 acpid 命令
* setup-ops - 运维节点配置
  * 安装运维常用的包
* setup-phy - 物理节点配置
  * 安装物理节点常用的包

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

# 检测存活
ansible all -i plays -m ping
# 进行操作
ansible-playbook adhoc.yaml -e 'task=setup-base' -i plays

# 实验完成销毁容器
ansible-playbook adhoc.yaml -e 'role=dev task=play-container-destory' -i localhost
```
