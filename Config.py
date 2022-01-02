import json


class Config(object):

    with open("key.json") as f:
        key_info = json.load(f)
    # API ID
    access_key_id = key_info["access_key_id"]
    # API 密钥
    access_key_secret = key_info["access_key_secret"]
    # 创建地域
    region_id = "cn-shanghai"
    # 端点ID
    endpoint_id = "ecs-cn-hangzhou.aliyuncs.com"
    # 实例规格
    instance_type = "ecs.g6.xlarge"
    # 出口带宽
    band_out = 2
    # 主机名
    host_name = "Cloud-PC"
    # 查询标签键
    label_key = "usage"
    # 查询标签值
    label_value = "cloud_system"
    # 默认安全组ID
    security_group_id = "sg-uf6d96bhl8c2489gaoqx"
