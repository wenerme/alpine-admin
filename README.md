# Alpine Admin
Ansible Role for Alpine Host

## 文件结构
* vault - 保存密钥相关内容
  * admin_rsa.pri - 加密后的私钥 - 控制机器需要 ssh-add
  * admin_rsa.pub - 管理员公钥 - setup-base 时如果存在会拷贝到主机
* files - 过程文件

## 准备工作

```bash
# ssh agent 添加 admin key
# 分别输入 vault 密码和 ssh key 密码
ansible-vault view vault/admin_rsa.pri | ssh-add -
```
