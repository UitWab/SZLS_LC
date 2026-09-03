from enum import StrEnum


class BeamStatus(StrEnum):
    """梁状态稳定编码；允许后续版本新增或废弃成员。"""

    UNPRODUCED = "UNPRODUCED"
    REBAR_BINDING = "REBAR_BINDING"
    REBAR_CHECK = "REBAR_CHECK"
    FORMWORK_CHECK = "FORMWORK_CHECK"
    CONCRETE_CASTING = "CONCRETE_CASTING"
    CURING = "CURING"
    TENSION_GROUTING = "TENSION_GROUTING"
    QUALITY_ACCEPTED = "QUALITY_ACCEPTED"
    STORED = "STORED"
    READY_TO_SHIP = "READY_TO_SHIP"
    TRANSPORTING = "TRANSPORTING"
    ARRIVED = "ARRIVED"
    ERECTING = "ERECTING"
    COMPLETED = "COMPLETED"


BEAM_STATUS_LABELS: dict[BeamStatus, str] = {
    BeamStatus.UNPRODUCED: "未生产",
    BeamStatus.REBAR_BINDING: "钢筋绑扎",
    BeamStatus.REBAR_CHECK: "钢筋验收",
    BeamStatus.FORMWORK_CHECK: "模板验收",
    BeamStatus.CONCRETE_CASTING: "混凝土浇筑",
    BeamStatus.CURING: "养护",
    BeamStatus.TENSION_GROUTING: "张拉压浆",
    BeamStatus.QUALITY_ACCEPTED: "成品验收",
    BeamStatus.STORED: "存梁",
    BeamStatus.READY_TO_SHIP: "待出厂",
    BeamStatus.TRANSPORTING: "运输中",
    BeamStatus.ARRIVED: "已到场",
    BeamStatus.ERECTING: "架设中",
    BeamStatus.COMPLETED: "架设完成",
}
