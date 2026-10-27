import pytest
from automation_engine.modules.idp_studio.core.db import SessionLocal
from automation_engine.modules.idp_studio.forms.registry import FormRegistry
from automation_engine.modules.idp_studio.extractors.classifier import detect_operative_statutory_branch
from automation_engine.modules.idp_studio.forms.filler import DynamicFormFiller

@pytest.fixture
def gnl1_schema():
    db = SessionLocal()
    schema = FormRegistry.get_form_schema('GNL-1', db)
    db.close()
    return schema

def test_gnl1_schema_has_field_7_and_full_compounding_fields(gnl1_schema):
    fields = gnl1_schema.get('fields', [])
    field_ids = [f['id'] for f in fields]
    
    # Field 7 must be present
    assert 'gnl1.main.field_7' in field_ids
    f7 = next(f for f in fields if f['id'] == 'gnl1.main.field_7')
    assert f7.get('canonical_no') == '7'
    assert f7.get('type') == 'textarea'
    assert f7.get('depends_on') is None  # Active across all use cases

    # Fields 8(d) through 8(l) must be present
    for letter in ['d', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't']:
        fid = f'gnl1.main.field_8{letter}'
        assert fid in field_ids, f'Missing {fid}'

def test_gnl1_branch_detection_compounding():
    text = (
        "RESOLVED THAT pursuant to Section 441 of the Companies Act, 2013, "
        "the company hereby makes an application for compounding of offence."
    )
    res = detect_operative_statutory_branch(text, candidate_options=[
        "Compounding of offences",
        "Extension of period of annual general meeting by three months",
        "Scheme of arrangement, amalgamation",
        "Others"
    ])
    assert res is not None
    assert res.get("recommended_branch") == "Compounding of offences"
    assert res.get("section_cited") == "Section 441"

def test_gnl1_branch_detection_agm_extension():
    text = (
        "RESOLVED THAT pursuant to Section 96 of the Companies Act, 2013, "
        "an application for extension of period of annual general meeting by three months be filed."
    )
    res = detect_operative_statutory_branch(text, candidate_options=[
        "Compounding of offences",
        "Extension of period of annual general meeting by three months",
        "Scheme of arrangement, amalgamation",
        "Others"
    ])
    assert res is not None
    assert res.get("recommended_branch") == "Extension of period of annual general meeting by three months"
    assert res.get("section_cited") == "Section 96(1)"

def test_gnl1_dag_pruning_under_compounding(gnl1_schema):
    filler = DynamicFormFiller()
    fields = gnl1_schema['fields']
    
    validated = {
        'gnl1.main.field_1a': {'id': 'gnl1.main.field_1a', 'value': 'Compounding of offences', 'status': 'populated'},
        'gnl1.main.field_8d': {'id': 'gnl1.main.field_8d', 'value': 'Suo-motu', 'status': 'populated'},
        'gnl1.main.field_8m': {'id': 'gnl1.main.field_8m', 'value': 'Yes', 'status': 'populated'}
    }
    active_map = filler._resolve_dag_dependencies(fields, validated)
    active_ids = [fid for fid, f in active_map.items() if f.get('is_active')]

    # Field 7 active
    assert 'gnl1.main.field_7' in active_ids
    # Field 8 and subfields active
    assert 'gnl1.main.field_8' in active_ids
    assert 'gnl1.main.field_8a' in active_ids
    assert 'gnl1.main.field_8d' in active_ids
    assert 'gnl1.main.field_8g' in active_ids
    assert 'gnl1.main.field_8n' in active_ids
    # 8o is pruned because 8m was 'Yes'
    assert 'gnl1.main.field_8o' not in active_ids
    # 9(a) and 10 are pruned because scenario is Compounding
    assert 'gnl1.main.field_9a' not in active_ids
    assert 'gnl1.main.field_10' not in active_ids
