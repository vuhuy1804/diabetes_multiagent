"""Validate curated_knowledge.json and synchronize DB_diabet.cypher.
Run: python backend/scripts/build_kg_seed.py --check | --write
Only intended for local, trusted, curated dataset. Never place patient data here.
"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
JSON_PATH=ROOT/'data/knowledge/curated_knowledge.json'
CYPHER_PATH=ROOT/'data/knowledge/DB_diabet.cypher'
ID=re.compile(r'^[a-z][a-z0-9_-]{1,63}$', re.IGNORECASE)

def cypher_string(value):
    if not isinstance(value,str) or '\n' in value or '\r' in value:
        raise ValueError('Cypher fields must be simple single-line text without semicolon')
    return "'"+value.replace('\\','\\\\').replace("'","\\'")+"'"

def validate(data):
    for key in ('sources','topics','facts','relations'):
        if not isinstance(data.get(key),list): raise ValueError(f'{key} must be list')
    ids={}
    for typ,key in [('source','sources'),('topic','topics'),('fact','facts')]:
        found=[]
        for obj in data[key]:
            if not isinstance(obj,dict) or not isinstance(obj.get('id'),str) or not ID.fullmatch(obj['id']):
                raise ValueError(f'bad {typ} id: {obj!r}')
            found.append(obj['id'])
        if len(found)!=len(set(found)): raise ValueError(f'duplicate {typ} id')
        ids[typ]=set(found)
    for s in data['sources']:
        if not s.get('url','').startswith('https://'): raise ValueError(f'missing https source: {s["id"]}')
        for col in ('title','publisher','url'): cypher_string(s[col])
    for t in data['topics']:
        for col in ('name','summary','category'): cypher_string(t[col])
        if isinstance(t.get('priority', 0), bool) or not isinstance(t.get('priority', 0), int) or not 0 <= t.get('priority', 0) <= 100:
            raise ValueError(f'invalid topic priority: {t["id"]}')
        if not isinstance(t.get('aliases'),list) or not t['aliases']:
            raise ValueError(f'missing aliases for {t["id"]}')
        for a in t['aliases']: cypher_string(a)
    for f in data['facts']:
        if f['topic_id'] not in ids['topic'] or f['source_id'] not in ids['source']:
            raise ValueError(f'orphan fact: {f["id"]}')
        cypher_string(f['text'])
    for r in data['relations']:
        if r['from_topic'] not in ids['topic'] or r['to_topic'] not in ids['topic'] or r['type']!='RELATED_TO':
            raise ValueError(f'invalid relation: {r!r}')
    return {k:len(data[k]) for k in ('topics','facts','sources','relations')}

def generate(data):
    validate(data)
    out=[f'// DB_diabet.cypher generated from curated_knowledge.json ({data["version"]}).',
         '// Educational source-backed facts only; no patient data.',
         'CREATE CONSTRAINT demo_topic_id IF NOT EXISTS FOR (t:Topic) REQUIRE t.id IS UNIQUE;',
         'CREATE CONSTRAINT demo_fact_id IF NOT EXISTS FOR (f:Fact) REQUIRE f.id IS UNIQUE;',
         'CREATE CONSTRAINT demo_source_id IF NOT EXISTS FOR (s:Source) REQUIRE s.id IS UNIQUE;',
         '']
    for s in data['sources']:
        out.append(f"MERGE (s:Source {{id: {cypher_string(s['id'])}}}) SET s.title = {cypher_string(s['title'])}, s.publisher = {cypher_string(s['publisher'])}, s.url = {cypher_string(s['url'])};")
    out.append('')
    for t in data['topics']:
        als='['+', '.join(cypher_string(a) for a in t['aliases'])+']'
        out.append(f"MERGE (t:Topic {{id: {cypher_string(t['id'])}}}) SET t.name = {cypher_string(t['name'])}, t.aliases = {als}, t.category = {cypher_string(t['category'])}, t.summary = {cypher_string(t['summary'])}, t.priority = {t.get('priority', 0)};")
    out.append('')
    for f in data['facts']:
        out.append(f"MERGE (f:Fact {{id: {cypher_string(f['id'])}}}) SET f.text = {cypher_string(f['text'])}, f.topic_id = {cypher_string(f['topic_id'])};")
        out.append(f"MATCH (t:Topic {{id: {cypher_string(f['topic_id'])}}}), (f:Fact {{id: {cypher_string(f['id'])}}}) MERGE (t)-[:HAS_FACT]->(f);")
        out.append(f"MATCH (f:Fact {{id: {cypher_string(f['id'])}}}), (s:Source {{id: {cypher_string(f['source_id'])}}}) MERGE (f)-[:SUPPORTED_BY]->(s);")
    out.append('')
    for r in data['relations']:
        out.append(f"MATCH (a:Topic {{id: {cypher_string(r['from_topic'])}}}), (b:Topic {{id: {cypher_string(r['to_topic'])}}}) MERGE (a)-[:RELATED_TO]->(b);")
    return '\n'.join(out)+'\n'

def main():
    p=argparse.ArgumentParser(description='Build or verify deterministic Neo4j seed')
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument('--check',action='store_true',help='check synchronized without editing')
    group.add_argument('--write',action='store_true',help='generate DB_diabet.cypher from curated_knowledge.json')
    opts=p.parse_args()
    data=json.loads(JSON_PATH.read_text(encoding='utf-8'))
    new=generate(data)
    if opts.write:
        CYPHER_PATH.write_text(new,encoding='utf-8')
        print('SEED WRITTEN',validate(data))
        return 0
    existing=CYPHER_PATH.read_text(encoding='utf-8') if CYPHER_PATH.exists() else ''
    if new!=existing:
        print('SEED OUT OF SYNC: run build_kg_seed.py --write')
        return 1
    print('SEED CHECK PASS',validate(data))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
