from backend_db.interfaces.contracts import DatabaseServices


def create_database_services() -> DatabaseServices:
    """A模块的组合入口；延迟导入具体实现，保持契约模块纯净。"""

    from backend_db.services import (
        AccessControlService,
        BeamPositionService,
        BeamService,
        BeamTypeService,
        ProjectService,
        ProcessDefinitionService,
        UserService,
        YardAreaService,
    )

    return DatabaseServices(
        projects=ProjectService(),
        processes=ProcessDefinitionService(),
        users=UserService(),
        access_control=AccessControlService(),
        beam_types=BeamTypeService(),
        yard_areas=YardAreaService(),
        beam_positions=BeamPositionService(),
        beams=BeamService(),
    )
