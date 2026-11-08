"""Export PX-pipeline-output.json files to a specialist review workbook.

Uses only Python's standard library; no inference, scoring or semantic merging.
"""
import argparse
import copy
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED

NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG = 'http://schemas.openxmlformats.org/package/2006/relationships'
CT = 'http://schemas.openxmlformats.org/package/2006/content-types'
ET.register_namespace('', NS)
ET.register_namespace('r', REL)
N = {'s': NS}
ROOT = Path(__file__).resolve().parents[1]


def tag(name):
    return f'{{{NS}}}{name}'


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def dimension(sheet, address):
    node = sheet.find(tag('dimension'))
    if node is None:
        node = ET.Element(tag('dimension'))
        sheet.insert(1 if sheet.find(tag('sheetPr')) is not None else 0, node)
    node.set('ref', address)


def fields_by_name(obj, names, label):
    fields = obj['fields']
    require(len(fields) == len(names), f'{label}: missing or extra fields')
    mapping = {f['field_name']: f for f in fields}
    require(len(mapping) == len(fields) and set(mapping) == set(names),
            f'{label}: duplicate, missing or unknown field names')
    return mapping


def check_values(field, label):
    require(isinstance(field['values'], list), f'{label}: values must be a list')
    for v in field['values']:
        require(isinstance(v['value'], str) and v['value'].strip(), f'{label}: empty value')
        require(isinstance(v['evidence'], list) and v['evidence'], f'{label}: missing evidence')
        for e in v['evidence']:
            require(isinstance(e['quote'], str) and e['quote'].strip(), f'{label}: empty quote')
            require(type(e['page_start']) is int and type(e['page_end']) is int
                    and 1 <= e['page_start'] <= e['page_end'], f'{label}: invalid pages')


def evidence_text(value):
    parts = []
    for e in value['evidence']:
        page = str(e['page_start']) if e['page_start'] == e['page_end'] else f"{e['page_start']}–{e['page_end']}"
        location = f'Página {page}'
        if e.get('section'):
            location += '; seção ' + e['section']
        if e.get('chunk_id'):
            location += '; ' + e['chunk_id']
        parts.append('“' + e['quote'] + '”\n' + location)
    return '\n\n'.join(parts)


def load_articles(run_dir, references_dir, schema):
    require(run_dir.is_dir(), f'Run directory not found: {run_dir}')
    paths = list(run_dir.glob('P*-pipeline-output.json'))
    require(paths, f'No PX-pipeline-output.json files in {run_dir}')
    names = [f['name'] for f in schema['fields']]
    require(names and len(set(names)) == len(names), 'Schema fields must be nonempty and unique')
    articles = []
    for path in paths:
        match = re.fullmatch(r'(P[1-9][0-9]*)-pipeline-output\.json', path.name)
        require(match is not None, f'Invalid article filename: {path.name}')
        sid = match[1]
        result = read_json(path)
        reference = read_json(references_dir / f'{sid}-human-reference.json')
        for label, document in [('output', result), ('reference', reference)]:
            if 'study_id' in document:
                require(document['study_id'] == sid, f'{sid}: {label} study_id differs from filename')
        extracted = fields_by_name(result, names, sid+' output')
        human = fields_by_name(reference, names, sid+' reference')
        records = {'L': [], 'H': []}
        summary = []
        for name in names:
            lf, hf = extracted[name], human[name]
            check_values(lf, sid+'/'+name)
            check_values(hf, sid+'/'+name+' reference')
            status = 'extracted' if lf['values'] else 'not_found_in_context'
            require(lf.get('status', status) == status, f'{sid}/{name}: invalid extraction status')
            summary.append([name, status, len(lf['values']), len(hf['values']), lf.get('notes') or ''])
            for kind, field in [('L', lf), ('H', hf)]:
                for value in field['values']:
                    identifier = f'{sid}-{kind}{len(records[kind])+1:04d}'
                    records[kind].append({'id': identifier, 'field': name, 'record': value})
        articles.append({'study_id': sid, 'records': records, 'field_summary': summary, 'schema': schema})
    return sorted(articles, key=lambda a: int(a['study_id'][1:]))



# Workbook layout is defined here; no external XLSX template is loaded.
STYLES_XML = """<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="4">
    <font>
      <sz val="11.0" />
      <color rgb="FF000000" />
      <name val="Carlito" />
      <scheme val="minor" />
    </font>
    <font>
      <sz val="11.0" />
      <color rgb="FF182B3A" />
      <name val="Arial" />
    </font>
    <font>
      <b />
      <sz val="15.0" />
      <color rgb="FF243C52" />
      <name val="Arial" />
    </font>
    <font>
      <b />
      <sz val="11.0" />
      <color rgb="FFFFFFFF" />
      <name val="Arial" />
    </font>
  </fonts>
  <fills count="5">
    <fill>
      <patternFill patternType="none" />
    </fill>
    <fill>
      <patternFill patternType="lightGray" />
    </fill>
    <fill>
      <patternFill patternType="solid">
        <fgColor rgb="FF243C52" />
        <bgColor rgb="FF243C52" />
      </patternFill>
    </fill>
    <fill>
      <patternFill patternType="solid">
        <fgColor rgb="FFFFF2CD" />
        <bgColor rgb="FFFFF2CD" />
      </patternFill>
    </fill>
    <fill>
      <patternFill patternType="solid">
        <fgColor rgb="FFEFF3F6" />
        <bgColor rgb="FFEFF3F6" />
      </patternFill>
    </fill>
  </fills>
  <borders count="2">
    <border />
    <border>
      <left />
      <right />
      <top />
      <bottom />
    </border>
  </borders>
  <cellStyleXfs count="1">
    <xf borderId="0" fillId="0" fontId="0" numFmtId="0" applyAlignment="1" applyFont="1" />
  </cellStyleXfs>
  <cellXfs count="9">
    <xf borderId="0" fillId="0" fontId="0" numFmtId="0" xfId="0" applyAlignment="1" applyFont="1" applyProtection="1">
      <alignment readingOrder="0" shrinkToFit="0" vertical="bottom" wrapText="0" />
      <protection locked="1" />
    </xf>
    <xf borderId="0" fillId="0" fontId="1" numFmtId="0" xfId="0" applyAlignment="1" applyFont="1" applyProtection="1">
      <alignment shrinkToFit="0" vertical="top" wrapText="1" />
      <protection locked="1" />
    </xf>
    <xf borderId="0" fillId="0" fontId="2" numFmtId="0" xfId="0" applyAlignment="1" applyFont="1" applyProtection="1">
      <alignment shrinkToFit="0" vertical="top" wrapText="0" />
      <protection locked="1" />
    </xf>
    <xf borderId="0" fillId="0" fontId="2" numFmtId="0" xfId="0" applyAlignment="1" applyFont="1" applyProtection="1">
      <alignment readingOrder="0" shrinkToFit="0" vertical="top" wrapText="0" />
      <protection locked="1" />
    </xf>
    <xf borderId="1" fillId="2" fontId="3" numFmtId="0" xfId="0" applyAlignment="1" applyBorder="1" applyFill="1" applyFont="1" applyProtection="1">
      <alignment shrinkToFit="0" vertical="top" wrapText="1" />
      <protection locked="1" />
    </xf>
    <xf borderId="0" fillId="0" fontId="1" numFmtId="0" xfId="0" applyAlignment="1" applyFont="1" applyProtection="1">
      <alignment readingOrder="0" shrinkToFit="0" vertical="top" wrapText="1" />
      <protection locked="1" />
    </xf>
    <xf borderId="1" fillId="3" fontId="1" numFmtId="0" xfId="0" applyAlignment="1" applyBorder="1" applyFill="1" applyFont="1" applyProtection="1">
      <alignment shrinkToFit="0" vertical="top" wrapText="1" />
      <protection locked="1" />
    </xf>
    <xf borderId="1" fillId="4" fontId="1" numFmtId="0" xfId="0" applyAlignment="1" applyBorder="1" applyFill="1" applyFont="1" applyProtection="1">
      <alignment shrinkToFit="0" vertical="top" wrapText="1" />
      <protection locked="1" />
    </xf>
    <xf borderId="1" fillId="3" fontId="1" numFmtId="0" xfId="0" applyAlignment="1" applyBorder="1" applyFill="1" applyFont="1" applyProtection="1">
      <alignment shrinkToFit="0" vertical="top" wrapText="1" />
      <protection locked="0" />
    </xf>
  </cellXfs>
  <cellStyles count="1">
    <cellStyle xfId="0" name="Normal" builtinId="0" />
  </cellStyles>
  <dxfs count="0" />
</styleSheet>"""

INSTRUCTION_LAYOUT = {'properties': ['<sheetPr xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><pageSetUpPr '
                '/></sheetPr>',
                '<sheetViews xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetView '
                'showGridLines="0" workbookViewId="0" /></sheetViews>',
                '<sheetFormatPr xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'customHeight="1" defaultColWidth="12.63" defaultRowHeight="15.0" />',
                '<cols xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><col '
                'customWidth="1" min="1" max="1" width="32.0" /><col customWidth="1" min="2" max="2" '
                'width="112.0" /></cols>',
                '<sheetProtection xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'sheet="1" objects="1" scenarios="1" selectLockedCells="0" selectUnlockedCells="0" />',
                '<printOptions xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" />',
                '<pageMargins xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'bottom="0.75" footer="0.0" header="0.0" left="0.7" right="0.7" top="0.75" />',
                '<pageSetup xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'orientation="landscape" />'],
 'rows': [(1, '15', [('A', '1', ''), ('B', '1', '')]),
          (2, '30.0', [('A', '2', 'Avaliação de extrações — Gender and Beyond'), ('B', '1', '')]),
          (3, '36.0', [('A', '4', 'Etapa / coluna'), ('B', '4', 'Como preencher')]),
          (4,
           '42.0',
           [('A', '1', 'IDs e valores'),
            ('B',
             '1',
             'P1-Lxx identifica um item da LLM; P1-Hxx, um valor do gabarito. Avalie o significado, não '
             'apenas as palavras. Dois textos equivalentes podem recuperar o mesmo valor.')]),
          (5,
           '42.0',
           [('A', '7', 'Correção do valor'),
            ('B',
             '7',
             'Escolha correto, parcialmente correto, incorreto ou em dúvida. Julgue o valor completo '
             'conforme o campo e o artigo.')]),
          (6,
           '42.0',
           [('A', '1', 'IDs do gabarito'),
            ('B',
             '1',
             'Digite um ou mais IDs separados por ponto e vírgula, por exemplo P1-Hxx; P1-Hyy. Se um valor '
             'válido não estiver no recorte, escreva “não está no recorte” e explique na observação. Não '
             'presuma que o recorte é o gabarito completo.')]),
          (7,
           '42.0',
           [('A', '7', 'Evidência'),
            ('B',
             '7',
             'Escolha completa, parcial, não sustenta ou em dúvida. Julgue a evidência fornecida, mesmo que '
             'exista um trecho melhor no artigo. As citações e a paginação física foram preservadas.')]),
          (8,
           '42.0',
           [('A', '1', 'Duplicação'),
            ('B',
             '1',
             'Escolha não, sim, parcial ou em dúvida. Se houver repetição, informe os IDs dos outros itens '
             'em “Duplicata de (IDs L)”. Mesmo com citações diferentes, os valores podem ser '
             'equivalentes.')]),
          (9,
           '42.0',
           [('A', '7', 'Agrupamento'),
            ('B',
             '7',
             'Escolha não, sim ou em dúvida. Se um item reunir valores independentes, liste-os na '
             'observação; em casos parciais, indique quais estão corretos e quais não estão.')]),
          (10,
           '42.0',
           [('A', '1', 'Cobertura'),
            ('B',
             '1',
             'Na tabela do gabarito, escolha coberto, parcialmente coberto, não encontrado nesta amostra ou '
             'em dúvida. Registre os IDs L correspondentes. Ausência nesta amostra não demonstra omissão na '
             'execução completa.')]),
          (11, '15', [('A', '1', ''), ('B', '1', '')]),
          (12, '27.75', [('A', '2', 'Definições dos campos — schema 4.6'), ('B', '1', '')]),
          (13, '15.75', [('A', '1', ''), ('B', '1', '')]),
          (14, '36.0', [('A', '4', 'Campo'), ('B', '4', 'Definição enviada ao modelo')]),
          (15, '48.0', [('A', '7', ''), ('B', '7', '')]),
          (16, '90.0', [('A', '1', ''), ('B', '1', '')])]}

ARTICLE_LAYOUT = {'properties': ['<sheetPr xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><pageSetUpPr '
                '/></sheetPr>',
                '<sheetViews xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetView '
                'showGridLines="0" workbookViewId="0" /></sheetViews>',
                '<sheetFormatPr xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'customHeight="1" defaultColWidth="12.63" defaultRowHeight="15.0" />',
                '<cols xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><col '
                'customWidth="1" min="1" max="1" width="14.0" /><col customWidth="1" min="2" max="2" '
                'width="24.0" /><col customWidth="1" min="3" max="3" width="34.5" /><col customWidth="1" '
                'min="4" max="4" width="68.0" /><col customWidth="1" min="5" max="5" width="24.0" /><col '
                'customWidth="1" min="6" max="6" width="27.88" /><col customWidth="1" min="7" max="7" '
                'width="21.0" /><col customWidth="1" min="8" max="8" width="17.0" /><col customWidth="1" '
                'min="9" max="9" width="21.0" /><col customWidth="1" min="10" max="10" width="19.0" /><col '
                'customWidth="1" min="11" max="11" width="45.0" /></cols>',
                '<sheetProtection xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'sheet="1" objects="1" scenarios="1" selectLockedCells="0" selectUnlockedCells="0" />',
                '<mergeCells xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'count="2"><mergeCell ref="A1:K1" /><mergeCell ref="A11:G11" /></mergeCells>',
                '<dataValidations '
                'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><dataValidation '
                'type="list" allowBlank="1" showInputMessage="1" showErrorMessage="1" prompt="Julgamento da '
                'especialista - Escolha uma opção. Deixe em branco até avaliar o item." '
                'sqref="G4:G9"><formula1>"completa,parcial,não sustenta,em '
                'dúvida"</formula1></dataValidation><dataValidation type="list" allowBlank="1" '
                'showInputMessage="1" showErrorMessage="1" prompt="Julgamento da especialista - Escolha uma '
                'opção. Deixe em branco até avaliar o item." sqref="E13:E16"><formula1>"coberto,parcialmente '
                'coberto,não encontrado nesta amostra,em dúvida"</formula1></dataValidation><dataValidation '
                'type="list" allowBlank="1" showInputMessage="1" showErrorMessage="1" prompt="Julgamento da '
                'especialista - Escolha uma opção. Deixe em branco até avaliar o item." '
                'sqref="E4:E9"><formula1>"correto,parcialmente correto,incorreto,em '
                'dúvida"</formula1></dataValidation><dataValidation type="list" allowBlank="1" '
                'showInputMessage="1" showErrorMessage="1" prompt="Julgamento da especialista - Escolha uma '
                'opção. Deixe em branco até avaliar o item." sqref="J4:J9"><formula1>"não,sim,em '
                'dúvida"</formula1></dataValidation><dataValidation type="list" allowBlank="1" '
                'showInputMessage="1" showErrorMessage="1" prompt="Julgamento da especialista - Escolha uma '
                'opção. Deixe em branco até avaliar o item." sqref="H4:H9"><formula1>"não,sim,parcial,em '
                'dúvida"</formula1></dataValidation></dataValidations>',
                '<printOptions xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" />',
                '<pageMargins xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'bottom="0.75" footer="0.0" header="0.0" left="0.7" right="0.7" top="0.75" />',
                '<pageSetup xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'orientation="landscape" />'],
 'rows': [(1, '27.75', [('A', '3', 'P1')]),
          (2,
           '15',
           [('A', '5', 'Avaliador:'),
            ('B', '8', ''),
            ('C', '1', 'Data da revisão:'),
            ('D', '8', ''),
            ('E', '1', ''),
            ('F', '1', ''),
            ('G', '1', ''),
            ('H', '1', ''),
            ('I', '1', ''),
            ('J', '1', ''),
            ('K', '1', '')]),
          (3,
           '36.0',
           [('A', '4', 'ID LLM'),
            ('B', '4', 'Campo'),
            ('C', '4', 'Texto extraído (value)'),
            ('D', '4', 'Evidências e localização'),
            ('E', '4', 'Correção do valor'),
            ('F', '4', 'IDs do gabarito (H)'),
            ('G', '4', 'Evidência'),
            ('H', '4', 'Duplicação'),
            ('I', '4', 'Duplicata de (IDs L)'),
            ('J', '4', 'Agrupamento'),
            ('K', '4', 'Observação')]),
          (4,
           '109.5',
           [('A', '7', ''),
            ('B', '7', ''),
            ('C', '7', ''),
            ('D', '7', ''),
            ('E', '8', ''),
            ('F', '8', ''),
            ('G', '8', ''),
            ('H', '8', ''),
            ('I', '8', ''),
            ('J', '8', ''),
            ('K', '8', '')]),
          (5,
           '109.5',
           [('A', '1', ''),
            ('B', '1', ''),
            ('C', '1', ''),
            ('D', '1', ''),
            ('E', '8', ''),
            ('F', '8', ''),
            ('G', '8', ''),
            ('H', '8', ''),
            ('I', '8', ''),
            ('J', '8', ''),
            ('K', '8', '')]),
          (11, '27.75', [('A', '3', 'Gabarito')]),
          (12,
           '36.0',
           [('A', '4', 'ID humano'),
            ('B', '4', 'Campo'),
            ('C', '4', 'Valor do gabarito'),
            ('D', '4', 'Evidências e localização'),
            ('E', '4', 'Cobertura'),
            ('F', '4', 'Itens correspondentes (IDs L)'),
            ('G', '4', 'Observação')]),
          (13,
           '109.5',
           [('A', '1', ''),
            ('B', '1', ''),
            ('C', '1', ''),
            ('D', '1', ''),
            ('E', '8', ''),
            ('F', '8', ''),
            ('G', '8', '')]),
          (14,
           '184.5',
           [('A', '7', ''),
            ('B', '7', ''),
            ('C', '7', ''),
            ('D', '7', ''),
            ('E', '8', ''),
            ('F', '8', ''),
            ('G', '8', '')])]}

class ReviewWorkbook:
    def __init__(self):
        self.files = {
            'xl/styles.xml': STYLES_XML.encode(),
            'xl/workbook.xml': f'<workbook xmlns="{NS}"><sheets/></workbook>'.encode(),
            'xl/_rels/workbook.xml.rels': (
                f'<Relationships xmlns="{PKG}"><Relationship Id="styles" '
                f'Type="{REL}/styles" Target="styles.xml"/></Relationships>'
            ).encode(),
            '_rels/.rels': (
                f'<Relationships xmlns="{PKG}"><Relationship Id="workbook" '
                f'Type="{REL}/officeDocument" Target="xl/workbook.xml"/></Relationships>'
            ).encode(),
            '[Content_Types].xml': (
                f'<Types xmlns="{CT}">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                '</Types>'
            ).encode(),
        }
        self.instructions = self.layout_sheet(INSTRUCTION_LAYOUT)
        self.article = self.layout_sheet(ARTICLE_LAYOUT)
        self.rows = {int(r.get('r')): r for r in self.article.find(tag('sheetData'))}
        self.wrapped_style = '1'
        self.validations = {v.get('sqref').split(':')[0]: v
                            for v in self.article.find(tag('dataValidations'))}

    def layout_sheet(self, layout):
        sheet = ET.Element(tag('worksheet'))
        for xml in layout['properties']:
            sheet.append(ET.fromstring(xml))
        sd = ET.Element(tag('sheetData'))
        # OOXML requires sheetData after cols and before protection/validation.
        cols = sheet.find(tag('cols'))
        sheet.insert(list(sheet).index(cols)+1, sd)
        for number, height, cells in layout['rows']:
            row = ET.SubElement(sd, tag('row'), {'r': str(number), 'ht': height, 'customHeight': '1'})
            for column, style, value in cells:
                cell = ET.SubElement(row, tag('c'), {'r': f'{column}{number}', 's': style})
                self.cell(cell, value or None)
        return sheet

    def text(self, cell):
        v = cell.find(tag('v'))
        if cell.get('t') == 'inlineStr':
            return ''.join(cell.find(tag('is')).itertext())
        return v.text if v is not None else ''

    def cell(self, cell, value):
        for child in list(cell):
            cell.remove(child)
        cell.attrib.pop('t', None)
        if value is None:
            return
        if isinstance(value, int):
            ET.SubElement(cell, tag('v')).text = str(value)
        else:
            value = str(value)
            require(len(value) <= 32767, 'Cell text exceeds XLSX limit; source must not be truncated')
            require(not re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', value), 'Invalid XML control character')
            cell.set('t', 'inlineStr')
            node = ET.SubElement(ET.SubElement(cell, tag('is')), tag('t'))
            node.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
            node.text = value

    def row(self, prototype, number, values=None):
        row = copy.deepcopy(prototype); row.set('r', str(number))
        for cell in row:
            col = re.match('[A-Z]+', cell.get('r'))[0]
            cell.set('r', col+str(number))
            if values is not None:
                self.cell(cell, values.get(col))
        return row

    def item_row(self, number, record, human=False):
        prototype = self.rows[(13 if number % 2 else 14) if human else (5 if number % 2 else 4)]
        value = record['record']
        values = dict(zip('ABCD', [record['id'], record['field'], value['value'], evidence_text(value)]))
        row = self.row(prototype, number, values)
        lines = max(sum(max(1, math.ceil(len(line)/65)) for line in values['D'].splitlines()),
                    math.ceil(len(values['C'])/34))
        row.set('ht', str(min(409, max(85, 15*lines+12)))); row.set('customHeight', '1')
        return row

    def article_sheet(self, article):
        sheet = copy.deepcopy(self.article); sd = sheet.find(tag('sheetData')); sd.clear()
        rows = article['records']; llm, human = rows['L'], rows['H']
        sd.append(self.row(self.rows[1], 1, {'A': article['study_id']}))
        sd.append(self.row(self.rows[2], 2, {'A': 'Avaliador:', 'C': 'Data da revisão:'}))
        sd.append(self.row(self.rows[3], 3))
        for i, record in enumerate(llm, 4):
            sd.append(self.item_row(i, record))
        htitle = len(llm)+5; hheader = htitle+1; hstart = hheader+1
        sd.append(self.row(self.rows[11], htitle))
        sd.append(self.row(self.rows[12], hheader))
        for i, record in enumerate(human, hstart):
            sd.append(self.item_row(i, record, True))
        # Explicit statuses prevent an empty extraction from disappearing from review.
        status_title = hstart+len(human)+1
        sd.append(self.row(self.rows[11], status_title, {'A': 'Situação dos campos'}))
        sd.append(self.row(self.rows[3], status_title+1, dict(zip('ABCDE',
            ['Campo', 'Status da extração', 'Itens da LLM', 'Valores do gabarito', 'Notas da extração']))))
        for i, values in enumerate(article['field_summary'], status_title+2):
            row = ET.Element(tag('row'), {'r': str(i), 'ht': '45', 'customHeight': '1'})
            for col, value in zip('ABCDE', values):
                # All status cells inherit a locked source style.
                cell = copy.deepcopy(self.rows[4][0]); cell.set('s', self.wrapped_style)
                cell.set('r', col+str(i)); self.cell(cell, value); row.append(cell)
            sd.append(row)
        end = status_title+1+len(article['field_summary'])
        dimension(sheet, f'A1:K{end}')
        merges = sheet.find(tag('mergeCells')); merges.clear(); merges.set('count', '3')
        for ref in ['A1:K1', f'A{htitle}:G{htitle}', f'A{status_title}:G{status_title}']:
            ET.SubElement(merges, tag('mergeCell'), {'ref': ref})
        dvs = sheet.find(tag('dataValidations')); dvs.clear()
        for key in ['E4', 'G4', 'H4', 'J4']:
            if llm:
                dv = copy.deepcopy(self.validations[key]); dv.set('sqref', f'{key}:{key[0]}{3+len(llm)}'); dvs.append(dv)
        if human:
            dv = copy.deepcopy(self.validations['E13']); dv.set('sqref', f'E{hstart}:E{hstart+len(human)-1}')
            dv.find(tag('formula1')).text = dv.find(tag('formula1')).text.replace('não encontrado nesta amostra', 'não encontrado')
            dvs.append(dv)
        dvs.set('count', str(len(dvs)))
        return sheet

    def instruction_sheet(self, schema):
        sheet = copy.deepcopy(self.instructions); sd = sheet.find(tag('sheetData'))
        prototypes = {int(r.get('r')): r for r in sd}
        sd.clear()
        for number in range(1, 15):
            if number not in prototypes:
                continue
            row = copy.deepcopy(prototypes[number])
            for cell in row:
                text = self.text(cell)
                if cell.get('r') == 'B6':
                    text = 'Digite IDs H separados por ponto e vírgula. Se um valor válido não estiver no gabarito, escreva “não está no gabarito” e explique na observação.'
                elif cell.get('r') == 'B10':
                    text = 'Escolha coberto, parcialmente coberto, não encontrado ou em dúvida. Registre os IDs L correspondentes. Avalie os valores dos arquivos fornecidos, conforme as definições abaixo.'
                elif cell.get('r') == 'A12':
                    text = 'Definições dos campos — schema '+schema['schema_version']
                self.cell(cell, text if text else None)
            sd.append(row)
        for i, field in enumerate(schema['fields'], 15):
            row = self.row(prototypes[16], i, {'A': field['name'], 'B': field['definition']})
            # Long identifiers use a wrapped, locked source style.
            row[0].set('s', self.wrapped_style)
            row.set('ht', str(min(409, max(65, math.ceil(len(field['definition'])/105)*16+12))))
            sd.append(row)
        dimension(sheet, f'A1:B{14+len(schema["fields"])}')
        return sheet

    def export(self, articles, path):
        data = dict(self.files)
        workbook = ET.fromstring(data['xl/workbook.xml']); sheets = workbook.find(tag('sheets')); sheets.clear()
        defined = workbook.find(tag('definedNames'))
        require(defined is None or len(defined) == 0, 'Defined names require explicit migration')
        rels = ET.fromstring(data['xl/_rels/workbook.xml.rels'])
        for rel in list(rels):
            if rel.get('Type', '').endswith('/worksheet'):
                rels.remove(rel)
        types = ET.fromstring(data['[Content_Types].xml'])
        for el in list(types):
            if el.get('PartName', '').startswith('/xl/worksheets/'):
                types.remove(el)
        for key in list(data):
            if key.startswith('xl/worksheets/'):
                del data[key]
        trees = [('Instruções', self.instruction_sheet(articles[0]['schema']))]
        trees += [(a['study_id'], self.article_sheet(a)) for a in articles]
        for i, (name, tree) in enumerate(trees, 1):
            rid = f'reviewSheet{i}'
            ET.SubElement(sheets, tag('sheet'), {'name': name, 'sheetId': str(i), f'{{{REL}}}id': rid})
            ET.SubElement(rels, f'{{{PKG}}}Relationship', {'Id': rid, 'Type': REL+'/worksheet', 'Target': f'worksheets/sheet{i}.xml'})
            ET.SubElement(types, f'{{{CT}}}Override', {'PartName': f'/xl/worksheets/sheet{i}.xml',
                'ContentType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml'})
            data[f'xl/worksheets/sheet{i}.xml'] = ET.tostring(tree, encoding='utf-8', xml_declaration=True)
        for key, tree in [('xl/workbook.xml', workbook), ('xl/_rels/workbook.xml.rels', rels), ('[Content_Types].xml', types)]:
            # Package metadata uses its own default namespace (Excel/OPC readers).
            ET.register_namespace('', PKG if tree is rels else CT if tree is types else NS)
            data[key] = ET.tostring(tree, encoding='utf-8', xml_declaration=True)
        ET.register_namespace('', NS)
        with ZipFile(path, 'x', ZIP_DEFLATED) as z:
            for key, value in data.items():
                z.writestr(key, value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True, help='Folder containing PX-pipeline-output.json files')
    parser.add_argument('--output', type=Path, help='XLSX destination; defaults to outputs/review.xlsx; existing names receive a numeric suffix')
    parser.add_argument('--references-dir', type=Path, default=ROOT/'data/references')
    parser.add_argument('--schema', type=Path, default=ROOT/'config/gender_and_beyond_schema.json')
    args = parser.parse_args()
    output = args.output or ROOT/'outputs/review.xlsx'
    try:
        require(output.suffix.lower() == '.xlsx', 'Output must be an .xlsx file')
        articles = load_articles(args.run_dir, args.references_dir, read_json(args.schema))
        workbook = ReviewWorkbook()
        output.parent.mkdir(parents=True, exist_ok=True)
        requested_output = output
        suffix = 0
        while True:
            try:
                workbook.export(articles, output)
                break
            except FileExistsError:
                suffix += 1
                output = requested_output.with_name(
                    f'{requested_output.stem}_{suffix}{requested_output.suffix}'
                )
        print(f'Saved: {output}')
    except (ValueError, KeyError, TypeError, OSError, ET.ParseError) as exc:
        parser.exit(1, f'Export failed: {exc}\n')


if __name__ == '__main__':
    main()
