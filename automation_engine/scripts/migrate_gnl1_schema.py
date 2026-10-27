import sqlite3
import json

def migrate_gnl1_schema():
    db_path = 'automation_engine/modules/idp_studio/idp_studio.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('SELECT template_id, template_name, fields_json FROM idp_templates WHERE template_name = "GNL-1"')
    row = cursor.fetchone()
    if not row:
        print("[!] GNL-1 template not found in database!")
        return

    tid, tname, fjson = row
    data = json.loads(fjson)
    orig_fields = data['fields']

    compounding_dep = {'field': 'gnl1.main.field_1a', 'operator': 'equals', 'value': 'Compounding of offences'}

    field_7 = {
        'id': 'gnl1.main.field_7',
        'canonical_no': '7',
        'label': 'Details of application',
        'type': 'textarea',
        'required': False,
        'options': [],
        'depends_on': None,
        'validation': {},
        'instructions': 'Enter detailed particulars of the application.'
    }

    fields_8d_to_8l = [
        {
            'id': 'gnl1.main.field_8d',
            'canonical_no': '8(d)',
            'label': 'Whether the application is being filed',
            'type': 'radio',
            'required': False,
            'options': ['Suo-motu', 'In pursuance to a notice'],
            'depends_on': compounding_dep,
            'validation': {},
            'instructions': 'Select whether filing Suo-motu or in pursuance to a notice.'
        },
        {
            'id': 'gnl1.main.field_8e',
            'canonical_no': '8(e)',
            'label': 'Notice number',
            'type': 'text',
            'required': False,
            'options': [],
            'depends_on': {'field': 'gnl1.main.field_8d', 'operator': 'equals', 'value': 'In pursuance to a notice'},
            'validation': {},
            'instructions': 'Enter notice number if filed in pursuance to notice.'
        },
        {
            'id': 'gnl1.main.field_8f',
            'canonical_no': '8(f)',
            'label': 'Date of the notice (DD/MM/YYYY)',
            'type': 'date',
            'required': False,
            'options': [],
            'depends_on': {'field': 'gnl1.main.field_8d', 'operator': 'equals', 'value': 'In pursuance to a notice'},
            'validation': {},
            'instructions': 'Enter date of the notice.'
        },
        {
            'id': 'gnl1.main.field_8g',
            'canonical_no': '8(g)',
            'label': 'Section of the Companies Act, 2013 under which application is being filed',
            'type': 'text',
            'required': False,
            'options': [],
            'depends_on': compounding_dep,
            'validation': {},
            'instructions': 'Enter relevant Section under which application is filed.'
        },
        {
            'id': 'gnl1.main.field_8h',
            'canonical_no': '8(h)',
            'label': 'If others, specify section',
            'type': 'text',
            'required': False,
            'options': [],
            'depends_on': compounding_dep,
            'validation': {},
            'instructions': 'Specify section if other.'
        },
        {
            'id': 'gnl1.main.field_8i',
            'canonical_no': '8(i)',
            'label': 'Brief description of the default',
            'type': 'textarea',
            'required': False,
            'options': [],
            'depends_on': compounding_dep,
            'validation': {},
            'instructions': 'Provide brief description of the default.'
        },
        {
            'id': 'gnl1.main.field_8j',
            'canonical_no': '8(j)',
            'label': 'Period of default – From (DD/MM/YYYY)',
            'type': 'date',
            'required': False,
            'options': [],
            'depends_on': compounding_dep,
            'validation': {},
            'instructions': 'Enter starting date of default.'
        },
        {
            'id': 'gnl1.main.field_8k',
            'canonical_no': '8(k)',
            'label': 'Period of default – To (DD/MM/YYYY)',
            'type': 'date',
            'required': False,
            'options': [],
            'depends_on': compounding_dep,
            'validation': {},
            'instructions': 'Enter ending date of default.'
        },
        {
            'id': 'gnl1.main.field_8l',
            'canonical_no': '8(l)',
            'label': 'Reasons that led to the default',
            'type': 'textarea',
            'required': False,
            'options': [],
            'depends_on': compounding_dep,
            'validation': {},
            'instructions': 'Provide reasons that led to the default.'
        }
    ]

    fields_8p_to_8s = [
        {
            'id': 'gnl1.main.field_8p',
            'canonical_no': '8(p)',
            'label': 'Reasons why compounding fee should not be levied',
            'type': 'textarea',
            'required': False,
            'options': [],
            'depends_on': compounding_dep,
            'validation': {},
            'instructions': 'State mitigating reasons / justification.'
        },
        {
            'id': 'gnl1.main.field_8q',
            'canonical_no': '8(q)',
            'label': 'Whether any investigation against the company has been initiated under the Companies Act',
            'type': 'radio',
            'required': False,
            'options': ['Yes', 'No'],
            'depends_on': compounding_dep,
            'validation': {},
            'instructions': 'Select Yes or No.'
        },
        {
            'id': 'gnl1.main.field_8r',
            'canonical_no': '8(r)',
            'label': 'If yes, specify the agency conducting the investigation',
            'type': 'select',
            'required': False,
            'options': ['SFIO', 'Others'],
            'depends_on': {'field': 'gnl1.main.field_8q', 'operator': 'equals', 'value': 'Yes'},
            'validation': {},
            'instructions': 'Select investigating agency.'
        },
        {
            'id': 'gnl1.main.field_8s',
            'canonical_no': '8(s)',
            'label': 'If Others, please specify the agencies',
            'type': 'text',
            'required': False,
            'options': [],
            'depends_on': {'field': 'gnl1.main.field_8r', 'operator': 'equals', 'value': 'Others'},
            'validation': {},
            'instructions': 'Specify other investigating agencies.'
        }
    ]

    new_fields = []
    for f in orig_fields:
        fid = f.get('id')
        if fid == 'gnl1.main.field_1a':
            f['options'] = [
                'Compounding of offences',
                'Extension of period of annual general meeting by three months',
                'Scheme of arrangement, amalgamation',
                'Others'
            ]
        elif fid == 'gnl1.main.field_2':
            f['options'] = ['Company', 'Foreign Company', 'Others']
        elif fid == 'gnl1.main.field_8':
            f['type'] = 'text'
            f['options'] = []
            f['depends_on'] = compounding_dep
        elif fid == 'gnl1.main.field_8a':
            f['options'] = ['Company', 'Director', 'Manager or Secretary or CEO or CFO', 'Others']
            f['depends_on'] = compounding_dep
        elif fid == 'gnl1.main.field_8b':
            f['depends_on'] = compounding_dep
        elif fid == 'gnl1.main.field_category':
            f['canonical_no'] = '8(c)(i)'
            f['options'] = ['Director', 'Manager', 'Secretary', 'CEO', 'CFO', 'Others']
            f['depends_on'] = compounding_dep
        elif fid == 'gnl1.main.field_director_identification_number_din':
            f['canonical_no'] = '8(c)(ii)'
            f['type'] = 'text'
            f['options'] = []
            f['depends_on'] = compounding_dep
        elif fid == 'gnl1.main.field_8m':
            f['options'] = ['Yes', 'No']
            f['depends_on'] = compounding_dep
        elif fid == 'gnl1.main.field_8n':
            f['type'] = 'textarea'
            f['options'] = []
            f['depends_on'] = {'field': 'gnl1.main.field_8m', 'operator': 'equals', 'value': 'Yes'}
        elif fid == 'gnl1.main.field_8o':
            f['type'] = 'textarea'
            f['options'] = []
            f['depends_on'] = {'field': 'gnl1.main.field_8m', 'operator': 'equals', 'value': 'No'}
        elif fid == 'gnl1.main.field_8t':
            f['type'] = 'textarea'
            f['depends_on'] = {'field': 'gnl1.main.field_8q', 'operator': 'equals', 'value': 'Yes'}

        new_fields.append(f)

        # Field 7 right after 6(d)
        if fid == 'gnl1.main.field_6d':
            new_fields.append(field_7)

        # 8(c)(iii) and 8(d) through 8(l) right after 8(c)(ii) DIN
        if fid == 'gnl1.main.field_director_identification_number_din':
            field_8c_name = {
                'id': 'gnl1.main.field_8c_name',
                'canonical_no': '8(c)(iii)',
                'label': 'Name of person for whom application is filed',
                'type': 'text',
                'required': False,
                'options': [],
                'depends_on': compounding_dep,
                'validation': {},
                'instructions': 'Enter name of person.'
            }
            new_fields.append(field_8c_name)
            new_fields.extend(fields_8d_to_8l)

        # 8(p) through 8(s) right after 8(o)
        if fid == 'gnl1.main.field_8o':
            new_fields.extend(fields_8p_to_8s)

    data['fields'] = new_fields
    updated_json = json.dumps(data, indent=2)

    cursor.execute('UPDATE idp_templates SET fields_json = ? WHERE template_name = "GNL-1"', (updated_json,))
    conn.commit()
    conn.close()
    print(f"[+] Successfully migrated GNL-1 template in idp_studio.db! Total fields now: {len(new_fields)}")

if __name__ == '__main__':
    migrate_gnl1_schema()
