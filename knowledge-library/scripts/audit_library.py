"""Read-only audit of library inputs; write reproducible audit evidence to reports/."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import re
import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports'
OUT.mkdir(exist_ok=True)

def read(name):
    return json.loads((ROOT / name).read_text(encoding='utf-8'))

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run():
    manifest = read('source-register.json')
    sources = manifest['sources']
    cases = read('failure-case-seeds.json')['cases']
    rubrics = read('assessment-rubrics.json')['rubrics']
    incidents = read('documented-case-notes.json')['cases']
    notes = [json.loads(x) for x in (ROOT/'curator-notes.jsonl').read_text(encoding='utf-8').splitlines()]
    source_by_id = {s['id']:s for s in sources}
    rubric_by_id = {r['rubric_id']:r for r in rubrics}
    checks=[]
    def check(name, failures, checked):
        checks.append(dict(check=name, status='PASS' if not failures else 'FAIL', checked=checked, failures=failures))
    for name, rows, key in [('source',sources,'id'),('case',cases,'case_id'),('rubric',rubrics,'rubric_id'),('incident',incidents,'id'),('note',notes,'chunk_id')]:
        counts=Counter(r[key] for r in rows)
        check(name+' IDs unique',[k for k,v in counts.items() if v>1],len(rows))
    urls=Counter(s['url'] for s in sources)
    check('Source URLs unique',[u for u,n in urls.items() if n>1],len(sources))
    refs=[(c['case_id'],r['source_id']) for c in cases for r in c['source_refs']]
    refs += [(r['rubric_id'],s['source_id']) for r in rubrics for s in r['source_refs']]
    refs += [(c['id'],c['source_id']) for c in incidents]
    refs += [(n['chunk_id'],n['source_id']) for n in notes]
    check('All source references resolve',[x for x in refs if x[1] not in source_by_id],len(refs))
    check('Case rubric and machine match',[c['case_id'] for c in cases if c['rubric_id'] not in rubric_by_id or rubric_by_id[c['rubric_id']]['machine']!=c['machine']],len(cases))
    check('Case locators present',[c['case_id'] for c in cases if not all(r.get('locator') for r in c['source_refs'])],len(cases))
    check('Case drafts not approved',[c['case_id'] for c in cases if c.get('generation_approved') or 'draft' not in c.get('review_status','')],len(cases))
    check('Rubric drafts not approved',[r['rubric_id'] for r in rubrics if r.get('instructor_approved')],len(rubrics))
    check('Source use flags remain unapproved',[s['id'] for s in sources if any(s.get(k) for k in ['external_inference_allowed','fine_tuning_allowed','redistribution_allowed','generation_approved'])],len(sources))
    check('Rubric group weights and criterion totals',[r['rubric_id'] for r in rubrics if sum(r['weights'].values())!=100 or sum(c['max_points'] for c in r['criteria'])!=100 or any(sum(c['max_points'] for c in r['criteria'] if c['group']==g)!=n for g,n in r['weights'].items())],len(rubrics))
    check('Rubric threshold within bounds',[r['rubric_id'] for r in rubrics if not 0<=r['draft_pass_threshold']<=100],len(rubrics))
    check('Mandatory safety gate specified',[r['rubric_id'] for r in rubrics if not r['safety_gate'].get('required')],len(rubrics))
    check('Curator notes map to cases and source hashes',[n['chunk_id'] for n in notes if n['case_id'] not in {c['case_id'] for c in cases} or n.get('source_sha256')!=source_by_id[n['source_id']].get('sha256')],len(notes))
    file_rows=[]
    for s in sources:
        if not s.get('file') or not (ROOT/s['file']).is_file(): continue
        p=ROOT/s['file']
        doc=pdfium.PdfDocument(str(p))
        page_count=len(doc)
        # Force each page to load; this is a structural check, not full content review.
        for index in range(page_count):
            page=doc[index]
            page.get_size()
            page.close()
        doc.close()
        file_rows.append(dict(source_id=s['id'],file=s['file'],sha256=digest(p),hash_matches=digest(p)==s.get('sha256'),bytes=p.stat().st_size,bytes_match=p.stat().st_size==s.get('bytes'),pages=page_count,pages_match=page_count==s.get('pdf_page_count'),pdf_signature=p.read_bytes()[:5]==b'%PDF-'))
    for key in ['hash_matches','bytes_match','pages_match','pdf_signature']:
        check('PDF '+key,[r['source_id'] for r in file_rows if not r[key]],len(file_rows))
    missing=[]
    for p in ROOT.glob('*.md'):
        for target in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
            if not target.startswith(('http:','https:','#')) and not (p.parent/target).is_file(): missing.append([p.name,target])
    check('Library Markdown local links resolve',missing,len(list(ROOT.glob('*.md'))))
    case_rows=[]
    specific={
      'HYD-05':'Choose one accumulator/circuit defect; the current target combines several mechanisms.',
      'HYD-06':'Choose whether the target is particulate contamination or its origin; alternatives currently describe origins.',
      'CONV-05':'Separate frame damage, side loading and pulley debris into mutually distinguishable fault definitions.',
      'CONV-06':'Vendor story supports mistracking and limited clearance; it does not establish a unique original root cause.'}
    for c in cases:
        case_rows.append(dict(case_id=c['case_id'],machine=c['machine'],target=c['private_target_fault'],source_id=c['source_refs'][0]['source_id'],locator=c['source_refs'][0]['locator'],model_assigned=bool(c.get('equipment_model_id')),numeric_parameters_defined=bool(c['project_authored_design']['numerical_parameters']),observation_placeholders=len(c['project_authored_design']['required_observation_placeholders']),review='Broad relationship supported; executable evidence missing',specific_issue=specific.get(c['case_id'],'Define stable diagnosis IDs, distinguishing observations and acceptance criteria.'),release_ready=False))
    summary=dict(sources=len(sources),current_scope_sources=sum(s['collection_scope']=='primary' for s in sources),downloaded_pdfs=len(file_rows),current_scope_pdfs=sum(source_by_id[r['source_id']]['collection_scope']=='primary' for r in file_rows),pdf_pages=sum(r['pages'] for r in file_rows),failed_download_records=[s['id'] for s in sources if s.get('download_status')=='failed'],cases=len(cases),cases_by_machine=dict(Counter(c['machine'] for c in cases)),cases_with_equipment_model=sum(r['model_assigned'] for r in case_rows),cases_with_numeric_parameters=sum(r['numeric_parameters_defined'] for r in case_rows),case_source_count=len({r['source_id'] for r in case_rows}),case_notes_with_no_source_hash=sum(not n.get('source_sha256') for n in notes),rubrics=len(rubrics),approved_rubrics=sum(r.get('instructor_approved',False) for r in rubrics),documented_cases=len(incidents),documented_cases_in_selected_categories=sum(c['machine'] in manifest['focus_machines'] for c in incidents),authored_quiz_questions_in_audited_files=0,checks_passed=sum(c['status']=='PASS' for c in checks),checks_failed=sum(c['status']=='FAIL' for c in checks))
    inputs=['source-register.json','failure-case-seeds.json','assessment-rubrics.json','documented-case-notes.json','curator-notes.jsonl','scripts/build_training_library.py','scripts/collect_sources.py']
    result=dict(audit_date='2026-10-06',timezone='Asia/Calcutta',scope='Current local library; all records and PDF structure checked, cited sections sampled against originals. No live simulator or full-manual engineering certification.',verdict='Suitable as a curated drafting library; not ready for released scored training.',summary=summary,checks=checks,pdf_checks=file_rows,case_review=case_rows,input_hashes={f:digest(ROOT/f) for f in inputs})
    (OUT/'audit-results.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))
    return result

if __name__=='__main__': run()
