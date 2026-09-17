from backend_db.interfaces.contracts import DatabaseServices


def create_database_services() -> DatabaseServices:
    """A模块的组合入口；延迟导入具体实现，保持契约模块纯净。"""

    from backend_db.services import (
        AccessControlService,
        BeamPositionService,
        BeamPositionWorkOrderService,
        BeamLifecycleEventService,
        BeamProcessExecutionService,
        BeamQualityInspectionService,
        BeamTransportHandoverService,
        BeamService,
        BeamTypeService,
        ProjectService,
        OperationAuditLogService,
        ProcessDefinitionService,
        UserService,
        YardAreaService,
    )

    return DatabaseServices(
        projects=ProjectService(),
        audit_logs=OperationAuditLogService(),
        processes=ProcessDefinitionService(),
        users=UserService(),
        access_control=AccessControlService(),
        beam_types=BeamTypeService(),
        yard_areas=YardAreaService(),
        beam_positions=BeamPositionService(),
        position_work_orders=BeamPositionWorkOrderService(),
        beam_events=BeamLifecycleEventService(),
        process_records=BeamProcessExecutionService(),
        quality_records=BeamQualityInspectionService(),
        transport_records=BeamTransportHandoverService(),
        beams=BeamService(),
    )
