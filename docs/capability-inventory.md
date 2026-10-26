# 能力清单（逐入口）

固定版本来源注册98 + 55；保留153个带来源前缀的入口，144个启用、9个明确禁用。另有6个统一控制/曲面组合工具，共159个唯一注册名称。**这是接口数量，不是153种不同建模能力，也不是153项实机通过。**

所有几何/实机验证均 NOT_RUN。Hub包装54个可调用转发签名全部离线校验；daiemon仅代表性point/offset/pocket/update分支做mock，不应从这些单测推断全部几何正确。

|工具|领域|启用|限制|
|---|---|---|---|
|daiemon__catia_add_component|assembly|是|实机未验证|
|daiemon__catia_add_new_part|assembly|是|实机未验证|
|daiemon__catia_fix_constraint|assembly|是|实机未验证|
|daiemon__catia_coincidence_constraint|assembly|否|Upstream ignores element1/element2; geometric binding not implemented.|
|daiemon__catia_offset_constraint|assembly|否|Geometric reference binding requires live validation; component-level fallback disabled.|
|daiemon__catia_angle_constraint|assembly|否|Geometric reference binding requires live validation.|
|daiemon__catia_move_component|assembly|是|实机未验证|
|daiemon__catia_list_components|assembly|是|实机未验证|
|daiemon__catia_list_constraints|assembly|是|实机未验证|
|daiemon__catia_diagnose|diagnostics|是|实机未验证|
|daiemon__catia_connect|document|否|Use auto_connect: attach only, no automatic application launch.|
|daiemon__catia_disconnect|document|否|Shared connection lifecycle is server-owned.|
|daiemon__catia_new_part|document|是|实机未验证|
|daiemon__catia_new_product|document|是|实机未验证|
|daiemon__catia_open_document|document|是|实机未验证|
|daiemon__catia_save_document|document|是|实机未验证|
|daiemon__catia_close_document|document|是|实机未验证|
|daiemon__catia_list_documents|document|是|实机未验证|
|daiemon__catia_get_active_document_info|document|是|实机未验证|
|daiemon__catia_new_drawing|drawing|是|实机未验证|
|daiemon__catia_drawing_list_view_geometry|drawing|是|实机未验证|
|daiemon__catia_drawing_add_dimension|drawing|是|实机未验证|
|daiemon__catia_drawing_generate_dimensions|drawing|是|实机未验证|
|daiemon__catia_drawing_list_dimensions|drawing|是|实机未验证|
|daiemon__catia_drawing_projection_view|drawing|是|实机未验证|
|daiemon__catia_drawing_section_view|drawing|是|实机未验证|
|daiemon__catia_drawing_detail_view|drawing|是|实机未验证|
|daiemon__catia_drawing_add_text|drawing|是|实机未验证|
|daiemon__catia_drawing_add_table|drawing|是|实机未验证|
|daiemon__catia_drawing_add_view|drawing|是|实机未验证|
|daiemon__catia_export|export|是|实机未验证|
|daiemon__catia_screenshot|export|否|Upstream dimensions/format claims unverified; prefer hub screenshot BMP.|
|daiemon__catia_set_view|export|是|实机未验证|
|daiemon__catia_fit_all|export|是|实机未验证|
|daiemon__catia_gsd_create_geoset|gsd|是|实机未验证|
|daiemon__catia_gsd_set_active_geoset|gsd|是|实机未验证|
|daiemon__catia_gsd_list_elements|gsd|是|实机未验证|
|daiemon__catia_gsd_point|gsd|是|实机未验证|
|daiemon__catia_gsd_line|gsd|是|实机未验证|
|daiemon__catia_gsd_plane_offset|gsd|是|实机未验证|
|daiemon__catia_gsd_plane_3points|gsd|是|实机未验证|
|daiemon__catia_gsd_spline|gsd|是|实机未验证|
|daiemon__catia_gsd_circle|gsd|是|实机未验证|
|daiemon__catia_gsd_project|gsd|是|实机未验证|
|daiemon__catia_gsd_intersection|gsd|是|实机未验证|
|daiemon__catia_gsd_multi_section_surface|gsd|是|实机未验证|
|daiemon__catia_gsd_sweep|gsd|是|实机未验证|
|daiemon__catia_gsd_extrude|gsd|是|实机未验证|
|daiemon__catia_gsd_revolve|gsd|是|实机未验证|
|daiemon__catia_gsd_fill|gsd|是|实机未验证|
|daiemon__catia_gsd_blend|gsd|是|实机未验证|
|daiemon__catia_gsd_offset_surface|gsd|是|实机未验证|
|daiemon__catia_gsd_join|gsd|是|实机未验证|
|daiemon__catia_gsd_split|gsd|是|实机未验证|
|daiemon__catia_gsd_trim|gsd|是|实机未验证|
|daiemon__catia_gsd_symmetry|gsd|是|实机未验证|
|daiemon__catia_gsd_thick_surface|gsd|是|实机未验证|
|daiemon__catia_gsd_close_surface|gsd|是|实机未验证|
|daiemon__catia_create_parameter|knowledge|是|实机未验证|
|daiemon__catia_set_formula|knowledge|是|实机未验证|
|daiemon__catia_list_relations|knowledge|是|实机未验证|
|daiemon__catia_delete_relation|knowledge|是|实机未验证|
|daiemon__catia_create_design_table|knowledge|是|实机未验证|
|daiemon__catia_measure_distance|measurement|否|Upstream unit multiplier is unverified; use Hub quality data with documented units.|
|daiemon__catia_get_inertia|measurement|是|实机未验证|
|daiemon__catia_get_bounding_box|measurement|否|Vertex sampling is not an exact surface bounding box.|
|daiemon__catia_get_parameters|measurement|是|实机未验证|
|daiemon__catia_set_parameter|measurement|是|实机未验证|
|daiemon__catia_update_part|measurement|是|实机未验证|
|daiemon__catia_pad|part_design|是|实机未验证|
|daiemon__catia_pocket|part_design|是|实机未验证|
|daiemon__catia_shaft|part_design|是|实机未验证|
|daiemon__catia_groove|part_design|是|实机未验证|
|daiemon__catia_fillet|part_design|是|实机未验证|
|daiemon__catia_chamfer|part_design|是|实机未验证|
|daiemon__catia_hole|part_design|是|实机未验证|
|daiemon__catia_rect_pattern|part_design|是|实机未验证|
|daiemon__catia_circ_pattern|part_design|是|实机未验证|
|daiemon__catia_user_pattern|part_design|是|实机未验证|
|daiemon__catia_mirror|part_design|是|实机未验证|
|daiemon__catia_shell|part_design|是|实机未验证|
|daiemon__catia_draft|part_design|是|实机未验证|
|daiemon__catia_thickness|part_design|是|实机未验证|
|daiemon__catia_delete_feature|part_design|是|实机未验证|
|daiemon__catia_list_features|part_design|是|实机未验证|
|daiemon__catia_list_edges|part_design|是|实机未验证|
|daiemon__catia_list_faces|part_design|是|实机未验证|
|daiemon__catia_create_sketch|sketcher|是|实机未验证|
|daiemon__catia_close_sketch|sketcher|是|实机未验证|
|daiemon__catia_sketch_line|sketcher|是|实机未验证|
|daiemon__catia_sketch_rectangle|sketcher|是|实机未验证|
|daiemon__catia_sketch_centered_rectangle|sketcher|是|实机未验证|
|daiemon__catia_sketch_circle|sketcher|是|实机未验证|
|daiemon__catia_sketch_arc|sketcher|是|实机未验证|
|daiemon__catia_sketch_spline|sketcher|是|实机未验证|
|daiemon__catia_sketch_point|sketcher|是|实机未验证|
|daiemon__catia_sketch_constraint|sketcher|是|实机未验证|
|daiemon__catia_sketch_get_geometry|sketcher|是|实机未验证|
|hub__catia_health_check|hub_modeling_surface|是|实机未验证|
|hub__catia_operation_status|hub_modeling_surface|是|实机未验证|
|hub__catia_connect|hub_modeling_surface|否|Use auto_connect: attach only.|
|hub__catia_list_documents|hub_modeling_surface|是|实机未验证|
|hub__catia_create_part|hub_modeling_surface|是|实机未验证|
|hub__catia_create_product|hub_modeling_surface|是|实机未验证|
|hub__catia_open_document|hub_modeling_surface|是|实机未验证|
|hub__catia_save_active|hub_modeling_surface|是|实机未验证|
|hub__catia_export_active|hub_modeling_surface|是|实机未验证|
|hub__catia_create_sketch|hub_modeling_surface|是|实机未验证|
|hub__catia_surface_capabilities|hub_modeling_surface|是|实机未验证|
|hub__catia_create_geometrical_set|hub_modeling_surface|是|实机未验证|
|hub__catia_create_3d_points|hub_modeling_surface|是|实机未验证|
|hub__catia_create_spline|hub_modeling_surface|是|实机未验证|
|hub__catia_create_offset_plane|hub_modeling_surface|是|实机未验证|
|hub__catia_create_connect_curve|hub_modeling_surface|是|实机未验证|
|hub__catia_create_loft|hub_modeling_surface|是|实机未验证|
|hub__catia_create_fill|hub_modeling_surface|是|实机未验证|
|hub__catia_join_surfaces|hub_modeling_surface|是|实机未验证|
|hub__catia_heal_surfaces|hub_modeling_surface|是|实机未验证|
|hub__catia_create_boundary|hub_modeling_surface|是|实机未验证|
|hub__catia_close_surface|hub_modeling_surface|是|实机未验证|
|hub__catia_thick_surface|hub_modeling_surface|是|实机未验证|
|hub__catia_check_surface_quality|hub_modeling_surface|是|实机未验证|
|hub__catia_add_pad|hub_modeling_surface|是|实机未验证|
|hub__catia_add_pocket|hub_modeling_surface|是|实机未验证|
|hub__catia_inspect_edges|hub_modeling_surface|是|实机未验证|
|hub__catia_add_edge_fillet|hub_modeling_surface|是|实机未验证|
|hub__catia_create_parametric_part|hub_modeling_surface|是|实机未验证|
|hub__catia_add_components|hub_modeling_surface|是|实机未验证|
|hub__catia_list_materials|hub_modeling_surface|是|实机未验证|
|hub__catia_apply_material|hub_modeling_surface|是|实机未验证|
|hub__catia_update_active|hub_modeling_surface|是|实机未验证|
|hub__catia_inspect_active|hub_modeling_surface|是|实机未验证|
|hub__catia_list_parameters|hub_modeling_surface|是|实机未验证|
|hub__catia_set_parameter|hub_modeling_surface|是|实机未验证|
|hub__catia_capture_view|hub_modeling_surface|是|实机未验证|
|hub__catia_close_active|hub_modeling_surface|是|实机未验证|
|hub__catia_analysis_catalog|analysis|是|实机未验证|
|hub__catia_create_analysis_document|analysis|是|实机未验证|
|hub__catia_inspect_analysis|analysis|是|实机未验证|
|hub__catia_add_analysis_case|analysis|是|实机未验证|
|hub__catia_run_analysis_transition|analysis|是|实机未验证|
|hub__catia_add_analysis_solution|analysis|是|实机未验证|
|hub__catia_add_analysis_set|analysis|是|实机未验证|
|hub__catia_add_analysis_entity|analysis|是|实机未验证|
|hub__catia_set_analysis_entity_value|analysis|是|实机未验证|
|hub__catia_add_analysis_mesh_part|analysis|是|实机未验证|
|hub__catia_set_analysis_mesh_specification|analysis|是|实机未验证|
|hub__catia_bind_analysis_mesh_support|analysis|是|实机未验证|
|hub__catia_bind_analysis_support|analysis|是|实机未验证|
|hub__catia_compute_analysis|analysis|是|实机未验证|
|hub__catia_create_analysis_result_image|analysis|是|实机未验证|
|hub__catia_export_analysis_result_data|analysis|是|实机未验证|
|hub__catia_build_analysis_report|analysis|是|实机未验证|

## 未宣称完成的第三项目意图及工程缺口

- chenlei源代码未复制（审查版本缺少LICENSE）；其REST/AI模板/异步占位没有作为已完成MCP能力移植。
- 多Body布尔、批量属性模板、事务型撤销/重做：待独立开发及实机验证，不提供假工具。
- Analysis提供原生17个工具入口，但材料实体SetReference/ApplyMaterialOnUserMaterial闭环仍有缺口；需已有有效Analysis模型，不能声称自动建模到可信结果的一键闭环。
- 稳定拓扑ID、生产级G2/A级质量证明、钣金展开/回弹、CAA插件、OAuth与多租户：未实现。
