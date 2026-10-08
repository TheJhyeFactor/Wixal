"""Record manually exercised CUA checks alongside actual packaged engine evidence."""
import asyncio,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];ART=ROOT/'artifacts/native/feature-acceptance'
async def main():
 reader,writer=await asyncio.open_unix_connection(ART/'workspace/engine.sock',limit=24*1024*1024)
 writer.write(b'{"id":"ui-evidence","method":"hello","params":{}}\n');await writer.drain()
 while line:=await asyncio.wait_for(reader.readline(),30):
  row=json.loads(line)
  if row['event']=='response' and row['data']['id']=='ui-evidence':break
 state=row['data']['result']['state'];session=next(s for s in state['sessions'] if s['id']==state['activeSession']);user=next(m for m in reversed(session['messages']) if m['role']=='user');answer=next(m for m in reversed(session['messages']) if m['role']=='assistant' and m.get('content'))
 assert user['imageIds'] and all(word in answer['content'].lower() for word in ('pink','blue','white','brown'))
 assert answer['usage']['eval_count']>0
 app=ROOT/'release/native/Wixal.app/Contents/MacOS/WixalNative'
 report=dict(status='passed',scope='Focused real packaged composer UI, manually exercised using CUA',appSha256=hashlib.sha256(app.read_bytes()).hexdigest(),checks=['incompatible model before image selection opens model picker','multiple actual image selection','actual image preview sheet','remove one image','draft and remaining image retained through Files navigation','draft and remaining image retained through app quit/relaunch','incompatible model send rejection preserves draft','actual oversized 12.1 MB file rejected with draft retained','image sent through visible composer and actual gemma3:12b answer shown','completed activity dock agrees with persisted actual result'],vision=dict(prompt=user['content'],imageIds=user['imageIds'],answer=answer['content'],usage=answer['usage']),remaining='Exhaustive themes, minimum size, keyboard-only, spoken VoiceOver, long tool sessions and assessment UI cancellation not certified by this record.')
 (ART/'composer-ui.json').write_text(json.dumps(report,indent=2));writer.close();await writer.wait_closed();print('PACKAGED_COMPOSER_UI_EVIDENCE_RECORDED')
asyncio.run(main())
