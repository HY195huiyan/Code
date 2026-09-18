import os
import anim_data
import importlib

importlib.reload(anim_data)


class AnimFile:
    def __init__(self, file_path=None):
        """
        初始化 AnimFile
        
        :param file_path: .anim 文件的完整路径
                         如果为 None，则尝试从当前工作目录查找 copyKeys.anim
        """
        # 如果没有传入文件路径，尝试在当前目录查找
        if file_path is None:
            # 使用当前工作目录
            current_dir = os.getcwd()
            file_path = os.path.join(current_dir, "copyKeys.anim")
            print(f"⚠️ 未指定文件路径，尝试使用: {file_path}")
        
        # 保存文件路径
        self.file_path = file_path
        
        # 检查文件是否存在
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"动画文件不存在: {self.file_path}")
        
        print(f"📖 正在读取动画文件: {self.file_path}")
        
        # 加载动画数据（传入文件路径）
        self.animData = anim_data.AnimData(self.file_path)
        self.timeUnit = self.getTimeUnit(self.animData.timeUnit)
        self.angularUnit = self.getAngularUnit(self.animData.angularUnit)
        self.nodes = self.animData.nodes
        self.keys = self.animData.keysAll
        self.nameInfo = self.animData.nameInfo
        self.addressInfo = self.animData.addressingInfo
        self.animCurveData = self.animData.animCurveData

    def getTimeUnit(self, timeUnit):
        timeUnitsToIndex = {
            '': 8,
            "hour": 1,
            "min": 2,
            "sec": 3,
            "millisec": 4,
            "game": 5,
            "film": 6,
            "pal": 7,
            "ntsc": 8,
            "show": 9,
            "palf": 10,
            "ntscf": 11
        }
        return timeUnitsToIndex.get(timeUnit, 8)

    def getAngularUnit(self, angularUnit):
        angularUnitsToIndex = {
            '': 2,
            "rad": 1,
            "deg": 2,
            "min": 3,
            "sec": 4,
        }
        return angularUnitsToIndex.get(angularUnit, 2)
