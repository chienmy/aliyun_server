import time

from Api import Api
from Logger import LOG


def retry_until(func, times: int, interval: float, args=()):
    """等待状态正确继续执行"""
    for i in range(times):
        time.sleep(interval)
        LOG.info("Test {0}/{1}: {2}".format(i, times, func.__name__))
        result = func(*args)
        if result:
            return result
    LOG.error("Retry {0} times failed: {1}".format(times, func.__name__))
    raise TimeoutError()


def start_instance_task(api: Api):
    # 检查实例状态
    instance = api.get_instance()
    if instance:
        LOG.error("Instance is running")
        return
    # 获取最低价格所在的可用区
    min_price_zone = api.min_price_zone()
    if not min_price_zone:
        return
    # 获取可用区下的交换机
    switch = api.get_region_switch(min_price_zone["zone_id"])
    if not switch:
        return
    # 获取系统镜像和数据盘快照
    system_image = api.get_system_image("Available")
    data_snapshot = api.get_snapshot("Data")
    if not (system_image and data_snapshot):
        return
    # 启动实例
    instance_id = api.run_instance(image_id=system_image["ImageId"],
                                   switch_id=switch["VSwitchId"],
                                   snapshot_id=data_snapshot["SnapshotId"])
    retry_until(api.check_instance_status, 30, 2, args=("Running",))
    LOG.info("Run instance success: " + instance_id)


def stop_instance_task(api: Api):
    instance = api.get_instance()
    if instance is None:
        LOG.error("No running instance")
        return
    # 查询系统盘
    system_disk = api.search_disk(instance["InstanceId"], "system")
    LOG.info("System Disk Id: " + system_disk["DiskId"])
    # 查询数据盘
    data_disk = api.search_disk(instance["InstanceId"], "data")
    LOG.info("Data Disk Id: " + data_disk["DiskId"])
    # 查询系统镜像使用的快照
    system_image = api.get_system_image("Available")
    old_system_snapshot_id = system_image["DiskDeviceMappings"]["DiskDeviceMapping"][0]["SnapshotId"]
    LOG.info("System Snapshot Id: " + old_system_snapshot_id)
    # 为当前数据盘创建新快照
    data_snapshot_id = api.create_snapshot(data_disk["DiskId"])
    retry_until(api.check_snapshot_status, 30, 30, args=(data_snapshot_id,))
    # 为当前系统盘创建新快照
    system_snapshot_id = api.create_snapshot(system_disk["DiskId"])
    retry_until(api.check_snapshot_status, 30, 30, args=(system_snapshot_id,))
    # 使用刚刚创建的系统盘快照创建新镜像
    system_image_id = api.create_image(system_snapshot_id)
    retry_until(api.check_image_status, 30, 5, args=(system_image_id,))
    # 停止实例运行
    api.stop_instance(instance["InstanceId"])
    retry_until(api.check_instance_status, 30, 2, args=("Stopped",))
    # 删除实例
    api.delete_instance(instance["InstanceId"])
    retry_until(api.check_instance_status, 30, 2, args=("Stopped", True))
    # 删除原有的系统盘镜像
    api.delete_image(instance["ImageId"])
    retry_until(api.check_image_status, 30, 5, args=(instance["ImageId"], True))
    # 删除原有的系统盘快照
    api.delete_snapshot(old_system_snapshot_id)
    retry_until(api.check_snapshot_status, 30, 5, args=(old_system_snapshot_id, True))
    # 删除原有的数据盘快照
    api.delete_snapshot(data_disk["SourceSnapshotId"])
    retry_until(api.check_snapshot_status, 30, 5, args=(data_disk["SourceSnapshotId"], True))


if __name__ == "__main__":
    stop_instance_task(Api())
