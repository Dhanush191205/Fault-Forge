"""Build reviewed-source-linked training drafts and a human-readable source index.

The cases, evidence plans and rubric weights are project-authored proposals.
Source documents are not treated as released scenarios or AI-use licenses.
"""
from pathlib import Path
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]

def write_json(name, value):
    (ROOT/name).write_text(json.dumps(value,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")

# Each concise source_fact states the referenced relationship. The remaining
# scenario fields describe new hypothetical exercise design, not an incident.
SEEDS=[
 ("CNC-01","CNC","Tool wear","CNC-HAAS-CHATTER","Excessive Tool Wear","Worn cutting tools can contribute to chatter.","Surface finish deteriorates during a simulated milling exercise.",["tool wear","long tool overhang","weak workholding"],["recorded edge-condition images","before/after finish comparison","tool-use history"]),
 ("CNC-02","CNC","Excessive tool overhang","CNC-HAAS-CHATTER","Tool or Tool Holder Too Long","Long tool assemblies can reduce stability.","A deep-pocket exercise develops vibration despite an apparently sound cutter.",["excessive overhang","tool wear","unsuitable cutting conditions"],["tool-and-holder configuration","approved setup alternatives","simulated finish response"]),
 ("CNC-03","CNC","Spindle-bearing degradation","CNC-HAAS-SPINDLE","Symptom Table; Bearings","Spindle-bearing problems are among the possible vibration causes.","A simulated spindle has unusual noise and inconsistent finish.",["bearing degradation","tool imbalance","toolholder/runout issue"],["recorded spindle observation","tool-independent comparison","reviewed bearing evidence"]),
 ("CNC-04","CNC","Axis lubrication loss","CNC-HAAS-BALLSCREW","Symptom Table; Lubrication","Poor ballscrew lubrication can accompany rough motion and positioning problems.","An axis moves unevenly and repeatability has changed.",["lubrication loss","ballscrew damage","thermal growth"],["lubrication-path inspection record","axis-motion history","repeatability evidence"]),
 ("CNC-05","CNC","Coolant-path obstruction","CNC-HAAS-COOLANT-NGC","Filter or Pump Blockage; Coolant Nozzle Blockage","Blockage is a possible cause of poor coolant delivery.","The simulated pump is commanded on but tool-area coolant delivery is poor.",["blocked flow path","low reservoir level","pump malfunction"],["reservoir and return-path record","filter/nozzle observations","simulated pump-status evidence"]),
 ("CNC-06","CNC","Tool runout","CNC-HAAS-SPINDLE","Symptom Table; Excessive Endmill Runout","Tool runout is one explanation investigated for finish and vibration problems.","A finish problem changes when the installed tool assembly changes.",["tool runout","spindle-bearing problem","tool wear"],["approved runout measurement record","toolholder-condition images","comparison across assemblies"]),
 ("HYD-01","Hydraulics","Air ingress at suction","HYD-REXROTH-GENERAL","PDF page 49, Table 3","Suction problems and foaming are possible hydraulic noise causes.","A simulated power unit becomes noisy and the fluid appearance changes.",["suction air ingress","mechanical coupling fault","unsuitable fluid condition"],["fluid appearance record","suction-path inspection record","noise and level trend"]),
 ("HYD-02","Hydraulics","Relief/pressure-control setting mismatch","HYD-REXROTH-GENERAL","PDF page 50, Tables 4 and 6","Pressure-valve settings can contribute to low pressure and heating.","A simulated actuator cannot achieve its expected output and fluid warms.",["setting mismatch","excessive internal loss","load/circuit mismatch"],["approved circuit reference","recorded pressure/return trend","configuration history"]),
 ("HYD-03","Hydraulics","Directional valve fails to switch","HYD-REXROTH-GENERAL","PDF page 50, Table 4","An incorrect valve spool position can prevent intended pressure delivery.","An actuator does not respond as expected despite a recorded command.",["valve switching fault","pressure-control fault","insufficient available flow"],["command and response record","valve-state evidence","circuit-path comparison"]),
 ("HYD-04","Hydraulics","Insufficient cooling","HYD-REXROTH-GENERAL","PDF page 50, Table 6","Insufficient heat rejection is a listed hydraulic overheating cause.","Fluid temperature rises during a simulated repeated-cycle task.",["cooling deficiency","continuous relief flow","changed operating conditions"],["temperature trend","cooling-flow/status record","duty-cycle comparison"]),
 ("HYD-05","Hydraulics","Accumulator/circuit mismatch","HYD-REXROTH-GENERAL","PDF page 50, Table 5","Accumulator conditions can contribute to frequent pump switching.","The pump cycles unusually often in the simulated system.",["accumulator mismatch","circuit volume/design issue","pressure-control behavior"],["pump-switching history","reviewed accumulator configuration","approved circuit specification"]),
 ("HYD-06","Hydraulics","Particulate contamination","HYD-REXROTH-GENERAL","PDF page 51, Table 7","Assembly, maintenance, environmental ingress and wear can introduce particles.","A fluid-condition record flags contamination after recent maintenance.",["maintenance-introduced dirt","environmental ingress","component wear debris"],["reviewed fluid-analysis record","maintenance chronology","ingress-path observations"]),
 ("CONV-01","Conveyor belt","Belt tension mismatch","CONV-DORNER-2200","PDF page 16, Troubleshooting","Incorrect belt tension can contribute to slipping.","Packages hesitate while the simulated drive continues to operate.",["belt tension mismatch","load excess","pulley condition"],["recorded belt-motion comparison","approved tension-check record","load history"]),
 ("CONV-02","Conveyor belt","Load-related stalling","CONV-DORNER-2200","PDF page 16, Troubleshooting","Excessive belt load can contribute to stalling or slip.","Transport becomes intermittent after a simulated product change.",["excessive load","intermittent jam","drive problem"],["product/load-change record","jam observation record","simulated transport response"]),
 ("CONV-03","Conveyor belt","Drive-pulley condition problem","CONV-DORNER-2200","PDF page 16, Troubleshooting","Drive-pulley wear or impacted dirt can contribute to slip.","A simulated belt loses motion transfer although its load is unchanged.",["pulley condition","tension mismatch","drive-train fault"],["pulley inspection images","recorded belt/drive motion","maintenance history"]),
 ("CONV-04","Conveyor belt","Accessory or guide interference","CONV-DORNER-2200","PDF page 16, Troubleshooting","Incorrect accessories or guides can damage the belt surface.","Fresh belt damage appears after a simulated guide adjustment.",["guide interference","foreign material","sharp product impact"],["damage-location images","guide-change record","product-impact evidence"]),
 ("CONV-05","Conveyor belt","Frame/side-load related V-guide damage","CONV-DORNER-2200","PDF page 16, Troubleshooting","Frame damage, pulley dirt and side loading can damage V-guides.","A simulated V-guided belt develops localized guide damage.",["frame/side-load condition","pulley debris","wrong application"],["frame inspection record","side-load configuration","V-guide damage pattern"]),
 ("CONV-06","Conveyor belt","Return-side mistracking in restricted space","CASE-FLEXCO-MINING","Problem; Solution; Result","A vendor reports return-side mistracking and edge damage in restricted space.","A bulk-conveyor exercise shows return-side rubbing where access is limited.",["incompatible tracking arrangement","application geometry","other alignment condition"],["layout and clearance record","belt-edge observation","trainer compatibility record"]),
]

def build():
    manifest=json.loads((ROOT/'source-register.json').read_text(encoding='utf-8'))
    sources={s['id']:s for s in manifest['sources']}
    sources['CNC-HAAS-MILL-2024']['extraction_status']='sampled_text_available_full_extraction_pending'
    sources['HYD-REXROTH-GENERAL']['extraction_status']='mixed_text_and_images_troubleshooting_OCR_required'
    sources['HYD-REXROTH-GENERAL']['reviewed_pdf_pages']=[1,49,50,51]
    sources['HYD-PARKER-VANE']['edition_note']='HY29-0106/UK, December 2011; T7/T67/T6 vane-pump families; diagnostic printed pages 37–40 verified through web fetch.'
    sources['HYD-PARKER-P1-PD']['edition_note']='HY28-2665-02/SVC/EN, July 2019; P1/PD A-Mod service information, confirmed in fetched text.'
    for sid in ['HYD-PARKER-VANE','HYD-PARKER-P1-PD']:
        sources[sid]['verification_status']='web_content_reviewed_local_PDF_download_HTTP_403'
    write_json('source-register.json',manifest)
    cases=[]
    for cid,machine,fault,sid,locator,fact,brief,alternatives,observations in SEEDS:
        rubric={'CNC':'RUBRIC-CNC-1','Hydraulics':'RUBRIC-HYD-1','Conveyor belt':'RUBRIC-CONV-1'}[machine]
        cases.append(dict(case_id=cid,version=1,machine=machine,case_kind='project_authored_source_linked_training_seed',review_status='draft_requires_instructor_review',generation_approved=False,equipment_model_id=None,public_brief=brief,private_target_fault=fault,source_fact=fact,source_refs=[dict(source_id=sid,locator=locator)],project_authored_design=dict(competing_causes=alternatives,required_observation_placeholders=observations,actions=['review_simulated_safety_plan','inspect_recorded_visual_evidence','interpret_recorded_measurements','compare_configuration_and_history','verify_proposed_virtual_correction'],numerical_parameters={},verification_rule='Instructor must define distinguishing evidence and a simulated before/after acceptance condition.'),rubric_id=rubric,limitations=['Hypothetical exercise; no measured incident data is attached.','Specific thresholds, controls and physical procedures require an applicable machine manual.','A single symptom must not automatically establish the private diagnosis.']))
    write_json('failure-case-seeds.json',dict(schema_version='ps015-failure-case-seeds/1.0',scope=manifest['focus_machines'],cases=cases))

    common=[
      dict(id='D1',group='diagnosis',max_points=20,criterion='Select the private target diagnosis from the scenario-defined answer set.',scoring_method='deterministic_answer_id_match'),
      dict(id='D2',group='diagnosis',max_points=15,criterion='Distinguish the target from the case-defined competing causes.',scoring_method='scenario_defined_structured_hypothesis_matches'),
      dict(id='D3',group='diagnosis',max_points=15,criterion='Link the conclusion to the scenario-defined causal explanation.',scoring_method='structured_causal_link_matches_or_instructor_review'),
      dict(id='E1',group='evidence',max_points=5,criterion='Collect the required distinguishing observations.',scoring_method='persisted_evidence_id_coverage'),
      dict(id='E2',group='evidence',max_points=5,criterion='Interpret units, source quality and equipment applicability correctly.',scoring_method='structured_checklist_matches'),
      dict(id='E3',group='evidence',max_points=5,criterion='Use collected observations to support or exclude hypotheses.',scoring_method='structured_observation_hypothesis_matches'),
      dict(id='E4',group='evidence',max_points=5,criterion='Verify the virtual correction and complete the investigation record.',scoring_method='persisted_verification_and_report_checklist'),
      dict(id='Q1',group='quiz',max_points=30,criterion='Answer five reviewed questions linked to the assessed competencies.',scoring_method='five_private_answer_key_matches_six_points_each'),
    ]
    machine_expectations={
      'CNC':dict(safety='Identify guarding, spindle/axis motion and electrical-service boundaries in the simulated safety plan.',evidence='Differentiate cutting-process, toolholding, spindle, axis and coolant evidence.',verification='Use the reviewed simulated finish, motion or coolant acceptance condition.'),
      'Hydraulics':dict(safety='Identify pressurized fluid, stored accumulator energy, temperature and electrical-drive hazards in the simulated plan.',evidence='Interpret the approved circuit, pressure/flow/temperature records and fluid-condition evidence.',verification='Use the reviewed simulated pressure, actuator response, cycling or thermal acceptance condition.'),
      'Conveyor belt':dict(safety='Identify nip points, unexpected start, guards and stored mechanical energy in the simulated plan.',evidence='Compare load, belt/drive motion, guides, frame, pulley and tracking observations.',verification='Use the reviewed simulated transport, slip, tracking or belt-condition acceptance condition.'),
    }
    rubrics=[]
    for machine,rid in [('CNC','RUBRIC-CNC-1'),('Hydraulics','RUBRIC-HYD-1'),('Conveyor belt','RUBRIC-CONV-1')]:
      rubrics.append(dict(rubric_id=rid,version=1,machine=machine,status='project_draft_not_an_official_certification_rubric',source_refs=[dict(source_id='RUB-WS-MECHANICS-2024',locator='Sections 1, 5, 6, 7'),dict(source_id='RUB-DGT-MMTM-CITS',locator='Learning outcomes; assessment criteria, PDF pages 12, 28 onward')],weights=dict(diagnosis=50,evidence=20,quiz=30),criteria=common,safety_gate=dict(required=True,points=0,pass_rule='All case-defined safety prerequisites must be completed before simulated investigation; attempted bypass is logged and requires remediation.',effect='A failed gate prevents a passed outcome even if numeric score exceeds the draft threshold.'),performance_levels=[dict(level='unsupported',fraction=0),dict(level='partial',fraction=0.5),dict(level='complete',fraction=1)],draft_pass_threshold=70,scoring_notes=['Weights and threshold are project design choices, not WorldSkills/DGT requirements.','Each criterion needs explicit per-case benchmarks before automatic scoring.','Free text requires instructor grading unless replaced by reviewed structured answers.','Elapsed time is recorded, not scored.','Safety and physical skills are assessed only to the extent represented in this simulation.'],machine_expectations=machine_expectations[machine],instructor_approved=False))
    write_json('assessment-rubrics.json',dict(schema_version='ps015-rubrics/1.0',rubrics=rubrics))

    incidents=[
      dict(id='DOCUMENTED-CONV-01',machine='Conveyor belt',source_id='CASE-FLEXCO-MINING',scope='Bulk mining; not interchangeable with Dorner flat-belt configuration.',summary='Flexco reports edge damage from return-side mistracking where limited space constrained trainer selection. Its reported remedy used a compatible compact trainer.',evidence_kind='vendor_reported_application_story',independent_validation=False,transfer_rule='Use the documented observation pattern; investigate fit and alignment without mandating a vendor product.'),
      dict(id='DOCUMENTED-DRIVE-01',machine='Motor',collection_scope='supplementary',source_id='FAIL-SKF-HANDBOOK',locator='PDF/printed pages 88–89',summary='SKF describes repeated bearing damage in a variable-speed paper-machine motor. Microscopy found electrical damage; investigation identified disconnected grounding.',evidence_kind='manufacturer_failure_investigation',independent_validation=False,transfer_rule='Use only as a bearing-drive mechanism example. Do not label it an observed CNC, hydraulic or conveyor failure.'),
    ]
    write_json('documented-case-notes.json',dict(schema_version='ps015-documented-cases/1.0',cases=incidents))

    # Short original notes, deliberately distinct from a bulk copy of manuals.
    notes=[]
    for case in cases:
      ref=case['source_refs'][0]
      note=dict(chunk_id='NOTE-'+case['case_id'],chunk_type='curator_paraphrase',machine=case['machine'],source_id=ref['source_id'],source_locator=ref['locator'],text=case['source_fact'],source_sha256=sources[ref['source_id']].get('sha256'),generation_approved=False,external_inference_allowed=False,case_id=case['case_id'])
      notes.append(note)
    (ROOT/'curator-notes.jsonl').write_text(''.join(json.dumps(n,ensure_ascii=False)+'\n' for n in notes),encoding='utf-8')

    rows=['# Source catalog — CNC, hydraulics and conveyor belts','', 'Collected 6 October 2026. Exact machine models are unspecified. Primary sources are reference candidates until equipment and rights checks are completed.','', '| ID | Source | Type / scope | Local material | Useful location |','|---|---|---|---|---|']
    for s in manifest['sources']:
      if s['collection_scope']!='primary':continue
      local=f"[{Path(s['file']).name}]({s['file']})" if s.get('file') and (ROOT/s['file']).is_file() else 'Verified reference link; local download unavailable' if s['download_status']=='failed' else 'Reference link'
      rows.append(f"| {s['id']} | [{s['title']}]({s['url']}) | {s['kind']} | {local} | {s['locator']} |")
    rows+=['','## Supplementary previous-scope references','','These remain available for context, but are not selected machine manuals for the updated project.','']
    for s in manifest['sources']:
      if s['collection_scope']=='primary':continue
      rows.append(f"- [{s['title']}]({s['url']}) — {', '.join(s['machines'])}.")
    rows+=['','## Access and extraction notes','','- Parker P1/PD and vane-pump PDFs returned HTTP 403 to the local downloader. Their web content was reviewed; no local PDF is claimed.','- Rexroth diagnostic pages 49–51 were visually reviewed. They are image content and require OCR plus table checking before bulk retrieval ingestion.','- The Rexroth host filename mentions 2025; the cover and embedded RE 07009-B/09.09 edition are older. File upload dates are not manual revisions.','- Haas spindle guidance includes a displayed inch/mm runout inconsistency in the retrieved page. No numerical limit from that line is imported into these drafts.','- CITS is an instructor-training curriculum. It is supplementary assessment design evidence, not a trainee qualification or a project certification.','- Public accessibility does not establish permission to redistribute a manual, send it to external inference, or fine-tune a model. Those flags remain false pending an established basis.','']
    (ROOT/'SOURCE-CATALOG.md').write_text('\n'.join(rows),encoding='utf-8')

    mapping=['# Failure seeds and competency mapping','', 'These 18 hypothetical seeds are project-authored drafts. They are not 18 documented industrial incidents.','', '| Seed | Machine | Private target | Source | Evidence to prepare |','|---|---|---|---|']
    for c in cases:
      mapping.append(f"| {c['case_id']} | {c['machine']} | {c['private_target_fault']} | {c['source_refs'][0]['source_id']} | {', '.join(c['project_authored_design']['required_observation_placeholders'])} |")
    mapping+=['','## Competencies','','C1: recognize simulated safety boundaries; C2: interpret applicable documentation; C3: collect and interpret evidence; C4: distinguish competing causes; C5: verify a virtual correction; C6: record and explain the investigation.','', 'Do not expose this private-target mapping through a trainee endpoint. Instructors must add distinguishing observations, approved numbers, quiz keys and transition rules before publication.','']
    (ROOT/'FAILURE-AND-COMPETENCY-MAP.md').write_text('\n'.join(mapping),encoding='utf-8')

    downloaded=[s for s in sources.values() if s.get('file') and (ROOT/s['file']).is_file()]
    report=dict(sources=len(sources),primary_sources=sum(s['collection_scope']=='primary' for s in sources.values()),downloaded_pdfs=len(downloaded),primary_downloaded_pdfs=sum(s['collection_scope']=='primary' for s in downloaded),failed_pdf_downloads=[s['id'] for s in sources.values() if s['download_status']=='failed'],training_seeds=len(cases),rubrics=len(rubrics),documented_case_notes=len(incidents),curator_notes=len(notes),validation=[])
    for c in cases:
      assert c['source_refs'][0]['source_id'] in sources
      assert c['rubric_id'] in {r['rubric_id'] for r in rubrics}
      assert not c['generation_approved']
    for r in rubrics:
      assert sum(r['weights'].values())==100
      assert sum(c['max_points'] for c in r['criteria'])==100
      for group,points in r['weights'].items(): assert sum(c['max_points'] for c in r['criteria'] if c['group']==group)==points
    for s in downloaded:
      assert hashlib.sha256((ROOT/s['file']).read_bytes()).hexdigest()==s['sha256']
    report['validation']=['All case source IDs and rubric IDs resolve.','All rubric weights and criterion maxima total 100, with matching group totals.','All downloaded PDF hashes match the register.','All cases are drafts with generation approval disabled.']
    write_json('collection-validation.json',report)
    print(json.dumps(report,indent=2))

if __name__=='__main__':build()
