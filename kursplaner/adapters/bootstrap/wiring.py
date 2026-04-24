from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from kursplaner.core.config.ui_preferences_store import load_ub_past_cutoff_time
from kursplaner.core.flows.lesson_transfer_flow import LessonTransferFlow
from kursplaner.core.flows.lzk_lesson_flow import LzkLessonFlow
from kursplaner.core.flows.plan_lesson_flow import PlanLessonFlow
from kursplaner.core.ports.repositories import LessonIndexRepository
from kursplaner.core.usecases.action_button_state_usecase import ActionButtonStateUseCase
from kursplaner.core.usecases.cleanup_lzk_expected_horizon_links_usecase import CleanupLzkExpectedHorizonLinksUseCase
from kursplaner.core.usecases.clear_selected_lesson_usecase import ClearSelectedLessonUseCase
from kursplaner.core.usecases.column_visibility_projection_usecase import ColumnVisibilityProjectionUseCase
from kursplaner.core.usecases.command_executor_usecase import CommandExecutorUseCase
from kursplaner.core.usecases.convert_to_ausfall_usecase import ConvertToAusfallUseCase
from kursplaner.core.usecases.convert_to_hospitation_usecase import ConvertToHospitationUseCase
from kursplaner.core.usecases.convert_to_lzk_usecase import ConvertToLzkUseCase
from kursplaner.core.usecases.create_plan_usecase import CreatePlanUseCase
from kursplaner.core.usecases.daily_course_log_usecase import DailyCourseLogUseCase
from kursplaner.core.usecases.daily_log_state_usecase import DailyLogStateUseCase
from kursplaner.core.usecases.export_expected_horizon_usecase import ExportExpectedHorizonUseCase
from kursplaner.core.usecases.export_lzk_expected_horizon_usecase import ExportLzkExpectedHorizonUseCase
from kursplaner.core.usecases.export_topic_units_pdf_usecase import ExportTopicUnitsPdfUseCase
from kursplaner.core.usecases.extend_plan_to_next_vacation_usecase import ExtendPlanToNextVacationUseCase
from kursplaner.core.usecases.find_markdown_for_selected_usecase import FindMarkdownForSelectedUseCase
from kursplaner.core.usecases.grid_cell_policy_usecase import GridCellPolicyUseCase
from kursplaner.core.usecases.history_usecase import HistoryUseCase
from kursplaner.core.usecases.invalidate_lesson_index_usecase import InvalidateLessonIndexUseCase
from kursplaner.core.usecases.invalidate_repository_caches_usecase import InvalidateRepositoryCachesUseCase
from kursplaner.core.usecases.lesson_commands_usecase import LessonCommandsUseCase
from kursplaner.core.usecases.lesson_context_query_usecase import LessonContextQueryUseCase
from kursplaner.core.usecases.lesson_edit_usecase import LessonEditUseCase
from kursplaner.core.usecases.lesson_transfer_usecase import LessonTransferUseCase
from kursplaner.core.usecases.list_lessons_usecase import ListLessonsUseCase
from kursplaner.core.usecases.load_last_ub_insights_usecase import LoadLastUbInsightsUseCase
from kursplaner.core.usecases.load_plan_detail_usecase import LoadPlanDetailUseCase
from kursplaner.core.usecases.mark_unit_as_ub_usecase import MarkUnitAsUbUseCase
from kursplaner.core.usecases.merge_selected_units_usecase import MergeSelectedUnitsUseCase
from kursplaner.core.usecases.move_selected_columns_usecase import MoveSelectedColumnsUseCase
from kursplaner.core.usecases.new_lesson_form_usecase import NewLessonFormUseCase
from kursplaner.core.usecases.new_lesson_usecase import NewLessonUseCase
from kursplaner.core.usecases.paste_lesson_usecase import PasteLessonUseCase
from kursplaner.core.usecases.path_settings_usecase import PathSettingsUseCase
from kursplaner.core.usecases.plan_commands_usecase import PlanCommandsUseCase
from kursplaner.core.usecases.plan_overview_query_usecase import PlanOverviewQueryUseCase
from kursplaner.core.usecases.plan_regular_lesson_usecase import PlanRegularLessonUseCase
from kursplaner.core.usecases.query_ub_achievements_usecase import QueryUbAchievementsUseCase
from kursplaner.core.usecases.query_ub_plan_usecase import QueryUbPlanUseCase
from kursplaner.core.usecases.rebuild_lesson_index_usecase import RebuildLessonIndexUseCase
from kursplaner.core.usecases.rebuild_plan_index_usecase import RebuildPlanIndexUseCase
from kursplaner.core.usecases.rebuild_subject_source_index_usecase import RebuildSubjectSourceIndexUseCase
from kursplaner.core.usecases.reconcile_ub_overview_usecase import ReconcileUbOverviewUseCase
from kursplaner.core.usecases.remove_unit_ub_link_usecase import RemoveUnitUbLinkUseCase
from kursplaner.core.usecases.rename_linked_file_for_row_usecase import RenameLinkedFileForRowUseCase
from kursplaner.core.usecases.repair_lesson_yaml_frontmatter_usecase import RepairLessonYamlFrontmatterUseCase
from kursplaner.core.usecases.restore_selected_from_cancel_usecase import RestoreSelectedFromCancelUseCase
from kursplaner.core.usecases.row_display_mode_usecase import RowDisplayModeUseCase
from kursplaner.core.usecases.save_cell_value_usecase import SaveCellValueUseCase
from kursplaner.core.usecases.split_selected_unit_usecase import SplitSelectedUnitUseCase
from kursplaner.core.usecases.subject_sources_usecase import SubjectSourcesUseCase
from kursplaner.core.usecases.sync_ub_development_focus_usecase import SyncUbDevelopmentFocusUseCase
from kursplaner.core.usecases.tracked_write_usecase import TrackedWriteUseCase
from kursplaner.infrastructure.export.expected_horizon_markdown_renderer import ExpectedHorizonMarkdownRenderer
from kursplaner.infrastructure.export.expected_horizon_pdf_renderer import ExpectedHorizonPdfRenderer
from kursplaner.infrastructure.export.topic_units_markdown_renderer import TopicUnitsMarkdownRenderer
from kursplaner.infrastructure.export.topic_units_pdf_renderer import TopicUnitsPdfRenderer
from kursplaner.infrastructure.repositories import FileSystemLessonIndexRepository
from kursplaner.infrastructure.repositories.markdown_repositories import (
    FileSystemCalendarRepository,
    FileSystemCommandRepository,
    FileSystemKompetenzkatalogRepository,
    FileSystemLessonFileRepository,
    FileSystemLessonRepository,
    FileSystemLessonSetupRepository,
    FileSystemPlanRepository,
    FileSystemSubjectSourceRepository,
    FileSystemUbRepository,
)


class CalendarTermResolver(Protocol):
    """Minimaler Vertrag für Halbjahresauflösung aus Datum."""

    def infer_term_from_date(self, start_date, calendar_dir):
        """Leitet das Halbjahr für ein Datum aus Kalenderdaten ab."""
        ...


@dataclass(frozen=True)
class CliDependencies:
    """Bündelt Abhängigkeiten für den CLI-Adapter."""

    calendar_repo: CalendarTermResolver
    create_plan_usecase: CreatePlanUseCase


@dataclass(frozen=True)
class GuiDependencies:
    """Bündelt alle GUI-seitig benötigten Use Cases/Flows.

    Diese Struktur ist der einzige Übergabepunkt vom Composition Root in den
    GUI-Adapter und verhindert direkte Infra-Instanziierung in GUI-Modulen.
    """

    max_history: int
    list_lessons_usecase: ListLessonsUseCase
    load_plan_detail_usecase: LoadPlanDetailUseCase
    action_button_state_usecase: ActionButtonStateUseCase
    lesson_transfer: LessonTransferUseCase
    lesson_commands: LessonCommandsUseCase
    plan_overview_query: PlanOverviewQueryUseCase
    lesson_context_query: LessonContextQueryUseCase
    convert_to_lzk: ConvertToLzkUseCase
    lzk_lesson_flow: LzkLessonFlow
    plan_regular_lesson: PlanRegularLessonUseCase
    plan_lesson_flow: PlanLessonFlow
    convert_to_ausfall: ConvertToAusfallUseCase
    convert_to_hospitation: ConvertToHospitationUseCase
    paste_lesson: PasteLessonUseCase
    lesson_transfer_flow: LessonTransferFlow
    command_executor: CommandExecutorUseCase
    history_usecase: HistoryUseCase
    tracked_write_usecase: TrackedWriteUseCase
    subject_sources: SubjectSourcesUseCase
    rebuild_plan_index: RebuildPlanIndexUseCase
    rebuild_subject_source_index: RebuildSubjectSourceIndexUseCase
    rebuild_lesson_index: RebuildLessonIndexUseCase
    invalidate_lesson_index: InvalidateLessonIndexUseCase
    repair_lesson_yaml_frontmatter_usecase: RepairLessonYamlFrontmatterUseCase
    invalidate_repository_caches: InvalidateRepositoryCachesUseCase
    clear_selected_lesson: ClearSelectedLessonUseCase
    split_selected_unit: SplitSelectedUnitUseCase
    merge_selected_units: MergeSelectedUnitsUseCase
    move_selected_columns: MoveSelectedColumnsUseCase
    find_markdown_for_selected: FindMarkdownForSelectedUseCase
    restore_selected_from_cancel: RestoreSelectedFromCancelUseCase
    save_cell_value: SaveCellValueUseCase
    rename_linked_file_for_row: RenameLinkedFileForRowUseCase
    path_settings_usecase: PathSettingsUseCase
    grid_cell_policy_usecase: GridCellPolicyUseCase
    row_display_mode_usecase: RowDisplayModeUseCase
    column_visibility_projection_usecase: ColumnVisibilityProjectionUseCase
    new_lesson_form_usecase: NewLessonFormUseCase
    new_lesson_usecase: NewLessonUseCase
    extend_plan_to_next_vacation_usecase: ExtendPlanToNextVacationUseCase
    export_topic_units_pdf_usecase: ExportTopicUnitsPdfUseCase
    export_topic_units_markdown_usecase: ExportTopicUnitsPdfUseCase
    export_expected_horizon_pdf_usecase: ExportExpectedHorizonUseCase
    export_expected_horizon_markdown_usecase: ExportExpectedHorizonUseCase
    export_lzk_expected_horizon_usecase: ExportLzkExpectedHorizonUseCase
    cleanup_lzk_expected_horizon_links_usecase: CleanupLzkExpectedHorizonLinksUseCase
    lesson_index_repo: LessonIndexRepository
    daily_course_log_usecase: DailyCourseLogUseCase
    daily_log_state_usecase: DailyLogStateUseCase
    mark_unit_as_ub_usecase: MarkUnitAsUbUseCase
    remove_unit_ub_link_usecase: RemoveUnitUbLinkUseCase
    reconcile_ub_overview_usecase: ReconcileUbOverviewUseCase
    query_ub_achievements_usecase: QueryUbAchievementsUseCase
    query_ub_plan_usecase: QueryUbPlanUseCase
    load_last_ub_insights_usecase: LoadLastUbInsightsUseCase


def build_gui_dependencies(*, max_history: int = 30) -> GuiDependencies:
    """Erzeugt die vollständige GUI-Verdrahtung im Composition Root.

    Hier werden konkrete Repository-Implementierungen instanziiert und in
    Use Cases/Flows injiziert. Diese Funktion ist die einzige erlaubte Stelle
    für diese Verdrahtung.
    """
    plan_repo = FileSystemPlanRepository()
    calendar_repo = FileSystemCalendarRepository()
    lesson_repo = FileSystemLessonRepository()
    lesson_index_repo = FileSystemLessonIndexRepository()
    lesson_file_repo = FileSystemLessonFileRepository()
    lesson_setup_repo = FileSystemLessonSetupRepository()
    subject_source_repo = FileSystemSubjectSourceRepository()
    ub_repo = FileSystemUbRepository()
    kompetenzkatalog_repo = FileSystemKompetenzkatalogRepository()

    plan_overview_query = PlanOverviewQueryUseCase(
        lesson_repo=lesson_repo,
        lesson_index_repo=lesson_index_repo,
        ub_repo=ub_repo,
    )
    list_lessons_usecase = ListLessonsUseCase(plan_repo=plan_repo, plan_overview_query=plan_overview_query)
    load_plan_detail_usecase = LoadPlanDetailUseCase(plan_repo=plan_repo, lesson_repo=lesson_repo, ub_repo=ub_repo)
    plan_commands = PlanCommandsUseCase(lesson_repo=lesson_repo)
    lesson_commands = LessonCommandsUseCase(lesson_repo=lesson_repo)
    lesson_edit = LessonEditUseCase(lesson_repo=lesson_repo)
    lesson_transfer = LessonTransferUseCase(
        lesson_repo=lesson_repo,
        lesson_file_repo=lesson_file_repo,
    )
    lesson_context_query = LessonContextQueryUseCase(lesson_repo=lesson_repo)
    # Note: `lesson_index_repo` instantiated for incremental index usage; usecases will be migrated to it.
    subject_sources = SubjectSourcesUseCase(subject_source_repo=subject_source_repo)
    convert_to_lzk = ConvertToLzkUseCase(
        plan_commands=plan_commands,
        lesson_commands=lesson_commands,
        plan_repo=plan_repo,
        lesson_transfer=lesson_transfer,
    )
    lzk_lesson_flow = LzkLessonFlow(convert_to_lzk=convert_to_lzk)
    plan_regular_lesson = PlanRegularLessonUseCase(
        lesson_repo=lesson_repo,
        lesson_commands=lesson_commands,
        plan_repo=plan_repo,
        lesson_transfer=lesson_transfer,
        subject_sources=subject_sources,
        lesson_context_query=lesson_context_query,
    )
    plan_lesson_flow = PlanLessonFlow(plan_regular_lesson=plan_regular_lesson)
    convert_to_ausfall = ConvertToAusfallUseCase(
        plan_commands=plan_commands,
        lesson_repo=lesson_repo,
        plan_repo=plan_repo,
    )
    convert_to_hospitation = ConvertToHospitationUseCase(
        plan_repo=plan_repo,
        lesson_repo=lesson_repo,
        lesson_commands=lesson_commands,
        lesson_transfer=lesson_transfer,
    )
    paste_lesson = PasteLessonUseCase(
        lesson_repo=lesson_repo,
        plan_repo=plan_repo,
        plan_commands=plan_commands,
        lesson_transfer=lesson_transfer,
    )
    lesson_transfer_flow = LessonTransferFlow(paste_lesson=paste_lesson)

    command_repo = FileSystemCommandRepository()
    command_executor = CommandExecutorUseCase(command_repo=command_repo)
    history_usecase = HistoryUseCase(
        command_executor=command_executor,
        max_history=max_history,
    )
    tracked_write_usecase = TrackedWriteUseCase(history_usecase=history_usecase)
    rebuild_plan_index = RebuildPlanIndexUseCase(plan_repo=plan_repo)
    rebuild_subject_source_index = RebuildSubjectSourceIndexUseCase(subject_source_repo=subject_source_repo)
    rebuild_lesson_index = RebuildLessonIndexUseCase(lesson_index_repo=lesson_index_repo)
    invalidate_lesson_index = InvalidateLessonIndexUseCase(lesson_index_repo=lesson_index_repo)
    repair_lesson_yaml_frontmatter_usecase = RepairLessonYamlFrontmatterUseCase(lesson_repo=lesson_repo)
    invalidate_repository_caches = InvalidateRepositoryCachesUseCase(
        plan_repo=plan_repo,
        subject_source_repo=subject_source_repo,
    )
    clear_selected_lesson = ClearSelectedLessonUseCase(
        plan_repo=plan_repo,
        plan_commands=plan_commands,
    )
    split_selected_unit = SplitSelectedUnitUseCase(
        plan_repo=plan_repo,
        plan_commands=plan_commands,
    )
    merge_selected_units = MergeSelectedUnitsUseCase(
        plan_repo=plan_repo,
        plan_commands=plan_commands,
    )
    rename_linked_file_for_row = RenameLinkedFileForRowUseCase(
        plan_repo=plan_repo,
        lesson_transfer=lesson_transfer,
        lesson_repo=lesson_repo,
        ub_repo=ub_repo,
    )
    move_selected_columns = MoveSelectedColumnsUseCase(
        plan_repo=plan_repo,
        plan_commands=plan_commands,
        lesson_transfer=lesson_transfer,
        rename_linked_file_for_row=rename_linked_file_for_row,
    )
    action_button_state_usecase = ActionButtonStateUseCase(
        lesson_context_query=lesson_context_query,
        merge_selected_units=merge_selected_units,
        move_selected_columns=move_selected_columns,
    )
    # expose rename usecase to adapters
    find_markdown_for_selected = FindMarkdownForSelectedUseCase(
        plan_repo=plan_repo,
        lesson_transfer=lesson_transfer,
    )
    restore_selected_from_cancel = RestoreSelectedFromCancelUseCase(
        plan_repo=plan_repo,
        plan_commands=plan_commands,
    )
    row_display_mode_usecase = RowDisplayModeUseCase()
    column_visibility_projection_usecase = ColumnVisibilityProjectionUseCase()
    sync_ub_development_focus_usecase = SyncUbDevelopmentFocusUseCase(
        lesson_repo=lesson_repo,
        ub_repo=ub_repo,
    )
    save_cell_value = SaveCellValueUseCase(
        lesson_edit=lesson_edit,
        plan_repo=plan_repo,
        lesson_transfer=lesson_transfer,
        rename_linked_file_for_row=rename_linked_file_for_row,
        row_display_mode_usecase=row_display_mode_usecase,
        sync_ub_development_focus_usecase=sync_ub_development_focus_usecase,
    )
    path_settings_usecase = PathSettingsUseCase()
    grid_cell_policy_usecase = GridCellPolicyUseCase()
    create_plan_usecase = CreatePlanUseCase(
        plan_repo=plan_repo,
        calendar_repo=calendar_repo,
    )
    new_lesson_form_usecase = NewLessonFormUseCase(
        calendar_repo=calendar_repo,
        kompetenz_repo=kompetenzkatalog_repo,
    )
    new_lesson_usecase = NewLessonUseCase(
        create_plan_usecase=create_plan_usecase,
        plan_repo=plan_repo,
        lesson_setup_repo=lesson_setup_repo,
    )
    extend_plan_to_next_vacation_usecase = ExtendPlanToNextVacationUseCase(
        plan_repo=plan_repo,
        create_plan_usecase=create_plan_usecase,
    )
    export_topic_units_pdf_usecase = ExportTopicUnitsPdfUseCase(renderer=TopicUnitsPdfRenderer())
    export_topic_units_markdown_usecase = ExportTopicUnitsPdfUseCase(renderer=TopicUnitsMarkdownRenderer())
    export_expected_horizon_pdf_usecase = ExportExpectedHorizonUseCase(renderer=ExpectedHorizonPdfRenderer())
    export_expected_horizon_markdown_usecase = ExportExpectedHorizonUseCase(renderer=ExpectedHorizonMarkdownRenderer())
    export_lzk_expected_horizon_usecase = ExportLzkExpectedHorizonUseCase(
        lesson_repo=lesson_repo,
        export_markdown_usecase=export_expected_horizon_markdown_usecase,
        export_pdf_usecase=export_expected_horizon_pdf_usecase,
    )
    cleanup_lzk_expected_horizon_links_usecase = CleanupLzkExpectedHorizonLinksUseCase(lesson_repo=lesson_repo)
    daily_course_log_usecase = DailyCourseLogUseCase(
        plan_repo=plan_repo,
        lesson_repo=lesson_repo,
    )
    daily_log_state_usecase = DailyLogStateUseCase()
    mark_unit_as_ub_usecase = MarkUnitAsUbUseCase(
        lesson_repo=lesson_repo,
        ub_repo=ub_repo,
    )
    remove_unit_ub_link_usecase = RemoveUnitUbLinkUseCase(
        lesson_repo=lesson_repo,
        ub_repo=ub_repo,
    )
    reconcile_ub_overview_usecase = ReconcileUbOverviewUseCase(
        lesson_repo=lesson_repo,
        ub_repo=ub_repo,
    )
    query_ub_achievements_usecase = QueryUbAchievementsUseCase(
        ub_repo=ub_repo,
        past_cutoff_time_provider=load_ub_past_cutoff_time,
    )
    query_ub_plan_usecase = QueryUbPlanUseCase(
        ub_repo=ub_repo,
        plan_repo=plan_repo,
    )
    load_last_ub_insights_usecase = LoadLastUbInsightsUseCase(
        ub_repo=ub_repo,
        past_cutoff_time_provider=load_ub_past_cutoff_time,
    )

    return GuiDependencies(
        max_history=max_history,
        list_lessons_usecase=list_lessons_usecase,
        load_plan_detail_usecase=load_plan_detail_usecase,
        action_button_state_usecase=action_button_state_usecase,
        lesson_transfer=lesson_transfer,
        plan_overview_query=plan_overview_query,
        lesson_commands=lesson_commands,
        lesson_context_query=lesson_context_query,
        convert_to_lzk=convert_to_lzk,
        lzk_lesson_flow=lzk_lesson_flow,
        plan_regular_lesson=plan_regular_lesson,
        plan_lesson_flow=plan_lesson_flow,
        convert_to_ausfall=convert_to_ausfall,
        convert_to_hospitation=convert_to_hospitation,
        paste_lesson=paste_lesson,
        lesson_transfer_flow=lesson_transfer_flow,
        command_executor=command_executor,
        history_usecase=history_usecase,
        tracked_write_usecase=tracked_write_usecase,
        subject_sources=subject_sources,
        rebuild_plan_index=rebuild_plan_index,
        rebuild_subject_source_index=rebuild_subject_source_index,
        rebuild_lesson_index=rebuild_lesson_index,
        invalidate_lesson_index=invalidate_lesson_index,
        repair_lesson_yaml_frontmatter_usecase=repair_lesson_yaml_frontmatter_usecase,
        invalidate_repository_caches=invalidate_repository_caches,
        clear_selected_lesson=clear_selected_lesson,
        split_selected_unit=split_selected_unit,
        merge_selected_units=merge_selected_units,
        move_selected_columns=move_selected_columns,
        find_markdown_for_selected=find_markdown_for_selected,
        restore_selected_from_cancel=restore_selected_from_cancel,
        save_cell_value=save_cell_value,
        rename_linked_file_for_row=rename_linked_file_for_row,
        path_settings_usecase=path_settings_usecase,
        grid_cell_policy_usecase=grid_cell_policy_usecase,
        row_display_mode_usecase=row_display_mode_usecase,
        column_visibility_projection_usecase=column_visibility_projection_usecase,
        new_lesson_form_usecase=new_lesson_form_usecase,
        new_lesson_usecase=new_lesson_usecase,
        extend_plan_to_next_vacation_usecase=extend_plan_to_next_vacation_usecase,
        export_topic_units_pdf_usecase=export_topic_units_pdf_usecase,
        export_topic_units_markdown_usecase=export_topic_units_markdown_usecase,
        export_expected_horizon_pdf_usecase=export_expected_horizon_pdf_usecase,
        export_expected_horizon_markdown_usecase=export_expected_horizon_markdown_usecase,
        export_lzk_expected_horizon_usecase=export_lzk_expected_horizon_usecase,
        cleanup_lzk_expected_horizon_links_usecase=cleanup_lzk_expected_horizon_links_usecase,
        lesson_index_repo=lesson_index_repo,
        daily_course_log_usecase=daily_course_log_usecase,
        daily_log_state_usecase=daily_log_state_usecase,
        mark_unit_as_ub_usecase=mark_unit_as_ub_usecase,
        remove_unit_ub_link_usecase=remove_unit_ub_link_usecase,
        reconcile_ub_overview_usecase=reconcile_ub_overview_usecase,
        query_ub_achievements_usecase=query_ub_achievements_usecase,
        query_ub_plan_usecase=query_ub_plan_usecase,
        load_last_ub_insights_usecase=load_last_ub_insights_usecase,
    )


def build_cli_dependencies() -> CliDependencies:
    """Erzeugt die CLI-spezifische Verdrahtung im Composition Root."""
    plan_repo = FileSystemPlanRepository()
    calendar_repo = FileSystemCalendarRepository()
    return CliDependencies(
        calendar_repo=calendar_repo,
        create_plan_usecase=CreatePlanUseCase(
            plan_repo=plan_repo,
            calendar_repo=calendar_repo,
        ),
    )
