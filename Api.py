from datetime import datetime
from alibabacloud_ecs20140526.client import Client as Ecs20140526Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_ecs20140526 import models as ecs_models

from Config import Config
from Logger import LOG
from Utils import Utils


class Api(object):

    def __init__(self):
        config = open_api_models.Config(access_key_id=Config.access_key_id,
                                        access_key_secret=Config.access_key_secret,
                                        region_id=Config.region_id,
                                        endpoint=Config.endpoint_id)
        self.client = Ecs20140526Client(config)

    def zones_of_region(self):
        """获取地域下可创建实例的可用区ID"""
        req = ecs_models.DescribeZonesRequest(
            region_id=Config.region_id,
            instance_charge_type="PostPaid",
            spot_strategy="SpotWithPriceLimit",
        )
        res = self.client.describe_zones(req).to_map()["body"]
        zone_list = list(filter(lambda z: Config.instance_type in z["AvailableInstanceTypes"]["InstanceTypes"], res["Zones"]["Zone"]))
        zone_id_list = list(map(lambda z: z["ZoneId"], zone_list))
        LOG.info("Get {0} zones in {1}".format(len(zone_id_list), Config.region_id))
        return zone_id_list

    def min_price_zone(self):
        """根据过去一周内的价格计算最低的均价，并返回对应的可用区ID"""
        end_time, start_time = Utils.get_week_range()
        price_zone_list = []
        for zone_id in self.zones_of_region():
            req = ecs_models.DescribeSpotPriceHistoryRequest(
                region_id=Config.region_id,
                zone_id=zone_id,
                network_type="vpc",
                instance_type=Config.instance_type,
                start_time=start_time,
                end_time=end_time
            )
            res = self.client.describe_spot_price_history(req).to_map()["body"]
            price_list = list(map(lambda p: p["SpotPrice"], res["SpotPrices"]["SpotPriceType"]))
            if len(price_list) == 0:
                continue
            price_avg = sum(price_list) / len(price_list)
            LOG.info("Price in {0}: {1}".format(zone_id, price_avg))
            price_zone_list.append({
                "zone_id": zone_id,
                "price": price_avg
            })
        if len(price_zone_list) == 0:
            return None
        price_zone_list.sort(key=lambda a: a["price"])
        LOG.info("Choose zone: " + price_zone_list[0]["zone_id"])
        return price_zone_list[0]

    def get_system_image(self, status: str):
        """
        获取系统镜像ID，查找失败返回None
        :param status: Available, Creating, Waiting, CreateFailed
        """
        req = ecs_models.DescribeImagesRequest(
            region_id=Config.region_id,
            status=status,
            image_owner_alias="self",
            instance_type=Config.instance_type,
            tag=[ecs_models.DescribeImagesRequestTag(
                Config.label_key,
                Config.label_value
            )]
        )
        res = self.client.describe_images(req).to_map()["body"]

        if int(res["TotalCount"]) == 1:
            image = res["Images"]["Image"][0]
            LOG.info("Get image: " + image["ImageName"])
            return image
        else:
            LOG.error("Search system image failed")
            return None

    def get_snapshot(self, disk_type: str):
        """
        获取快照ID，查找失败返回None
        :param disk_type Data, System
        """
        req = ecs_models.DescribeSnapshotsRequest(
            region_id=Config.region_id,
            source_disk_type=disk_type,
            tag=[ecs_models.DescribeSnapshotsRequestTag(
                Config.label_key,
                Config.label_value
            )]
        )
        res = self.client.describe_snapshots(req).to_map()["body"]

        if int(res["TotalCount"]) == 1:
            snapshot = res["Snapshots"]["Snapshot"][0]
            LOG.info("Get Snapshot: " + snapshot["SnapshotName"])
            return snapshot
        else:
            LOG.error("Search data snapshot failed")
            return None

    def get_region_switch(self, zone_id: str):
        """
        获取可用区对应的交换机ID
        :param zone_id 可用区ID
        """
        req = ecs_models.DescribeVSwitchesRequest(
            region_id=Config.region_id,
            zone_id=zone_id
        )
        res = self.client.describe_vswitches(req).to_map()["body"]
        if int(res["TotalCount"]) == 1:
            switch = res["VSwitches"]["VSwitch"][0]
            LOG.info("Get switch {0} in {1}".format(switch["VSwitchName"], zone_id))
            return switch
        else:
            LOG.error("Search v_switch failed")
            return None

    def get_instance(self):
        """
        根据标签获取实例，实例不存在则返回None
        """
        req = ecs_models.DescribeInstancesRequest(
            region_id=Config.region_id,
            tag=[ecs_models.DescribeInstancesRequestTag(
                Config.label_key,
                Config.label_value
            )]
        )
        res = self.client.describe_instances(req).to_map()["body"]
        if int(res["TotalCount"]) == 1:
            return res["Instances"]["Instance"][0]
        else:
            LOG.error("Search instance failed")
            return None

    def run_instance(self, image_id: str, switch_id: str, snapshot_id: str):
        """
        启动并运行实例
        """
        req = ecs_models.RunInstancesRequest(
            region_id=Config.region_id,
            image_id=image_id,
            instance_type=Config.instance_type,
            security_group_id=Config.security_group_id,
            v_switch_id=switch_id,
            instance_name=Config.host_name + Utils.get_today_date(),
            internet_max_bandwidth_out=Config.band_out,
            host_name=Config.host_name,
            password_inherit=True,
            internet_charge_type="PayByBandwidth",
            system_disk=ecs_models.RunInstancesRequestSystemDisk(
                size=30,
                category="cloud_efficiency"
            ),
            amount=1,
            spot_strategy="SpotWithPriceLimit",
            spot_duration=1,
            spot_price_limit=1.000,
            instance_charge_type="PostPaid",
            tag=[ecs_models.RunInstancesRequestTag(
                Config.label_key,
                Config.label_value
            )],
            data_disk=[ecs_models.RunInstancesRequestDataDisk(
                auto_snapshot_policy_id="",
                snapshot_id=snapshot_id,
                size=20,
                category="cloud_efficiency"
            )]
        )
        res = self.client.run_instances(req).to_map()["body"]
        return res["InstanceIdSets"]["InstanceIdSet"][0]

    def search_disk(self, instance_id: str, disk_type: str):
        """
        搜索实例下挂载的云盘
        """
        req = ecs_models.DescribeDisksRequest(
            region_id=Config.region_id,
            instance_id=instance_id,
            disk_type=disk_type
        )
        res = self.client.describe_disks(req).to_map()["body"]
        if int(res["TotalCount"]) == 1:
            return res["Disks"]["Disk"][0]
        else:
            LOG.error("Search disks failed")
            return None

    def create_snapshot(self, disk_id: str):
        """
        创建云盘的快照
        """
        req = ecs_models.CreateSnapshotRequest(
            disk_id=disk_id,
            snapshot_name="cloud_system_snapshot",
            tag=[ecs_models.CreateSnapshotRequestTag(
                Config.label_key,
                Config.label_value
            )]
        )
        res = self.client.create_snapshot(req).to_map()["body"]
        return res["SnapshotId"]

    def create_image(self, snapshot_id: str):
        """
        从快照创建自定义镜像
        """
        req = ecs_models.CreateImageRequest(
            region_id=Config.region_id,
            snapshot_id=snapshot_id,
            image_name="CloudSystem{0}".format(datetime.now().strftime("%Y%m%d")),
            tag=[ecs_models.CreateImageRequestTag(
                Config.label_key,
                Config.label_value
            )]
        )
        res = self.client.create_image(req).to_map()["body"]
        return res["ImageId"]

    def stop_instance(self, instance_id: str):
        """
        停止一个实例
        """
        req = ecs_models.StopInstanceRequest(
            instance_id=instance_id
        )
        self.client.stop_instance(req)

    def check_instance_status(self, status: str, reverse=False):
        """
        检查实例状态
        """
        instance = self.get_instance()
        if instance and instance["Status"] == status:
            return reverse ^ True
        return reverse ^ False

    def check_image_status(self, image_id: str, reverse=False):
        """
        检查镜像状态是否可用
        """
        req = ecs_models.DescribeImagesRequest(
            region_id=Config.region_id,
            status="Available",
            image_id=image_id
        )
        res = self.client.describe_images(req).to_map()["body"]
        if int(res["TotalCount"]) == 1:
            return reverse ^ True
        else:
            return reverse ^ False

    def check_snapshot_status(self, snapshot_id: str, reverse=False):
        """
        检查快照状态是否已完成创建
        """
        req = ecs_models.DescribeSnapshotsRequest(
            region_id=Config.region_id,
            snapshot_ids='["{0}"]'.format(snapshot_id),
            status="accomplished"
        )
        res = self.client.describe_snapshots(req).to_map()["body"]
        # 只有一个结果时表明搜索正确
        if int(res["TotalCount"]) == 1:
            return reverse ^ True
        else:
            return reverse ^ False

    def delete_instance(self, instance_id: str):
        """删除实例"""
        req = ecs_models.DeleteInstanceRequest(
            instance_id=instance_id
        )
        self.client.delete_instance(req)

    def delete_image(self, image_id: str):
        """删除镜像"""
        req = ecs_models.DeleteImageRequest(
            region_id=Config.region_id,
            image_id=image_id,
            force=True
        )
        self.client.delete_image(req)

    def delete_snapshot(self, snapshot_id: str):
        """删除快照"""
        req = ecs_models.DeleteSnapshotRequest(
            snapshot_id=snapshot_id
        )
        self.client.delete_snapshot(req)
