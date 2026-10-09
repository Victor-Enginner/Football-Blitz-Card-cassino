import {test} from 'node:test';
import assert from 'node:assert/strict';
import {summarize, advance, healthOf} from './monitor.mjs';
const events = outcomes => outcomes.map((outcome,i)=>({event_id:String(i),round_id:String(i),session_id:'paper',outcome,observed_at:new Date(1700000000000+i*30000).toISOString()}));
test('draw and other side break consecutive outcomes',()=>{
  assert.equal(summarize(events(['home','home','draw','home','home'])).count,2);
  assert.deepEqual(summarize(events(['away','away','draw'])),{outcome:null,count:0,started_at:null});
  assert.equal(summarize(events(['home','home','away'])).count,1);
});
test('4th and 5th observed results, then reset; repeated polling emits nothing',()=>{
  const rows=events(['home','home','home','home','home','draw']);
  const result=advance({session_id:'paper',cursor:'2'},{session_id:'paper',events:rows});
  assert.deepEqual(result.notices.map(n=>n.kind),['historical_sequence','historical_sequence','sequence_reset']);
  assert.deepEqual(advance(result.state,{session_id:'paper',events:rows}).notices,[]);
});
test('startup and session switch do not replay historical alerts',()=>{
  const history={session_id:'paper',events:events(['away','away','away','away'])};
  assert.deepEqual(advance({},history).notices,[]);
  assert.deepEqual(advance({session_id:'different',cursor:'1'},history).notices,[]);
});
test('gaps and out of order timestamps interrupt continuity',()=>{
  const rows=events(['home','home','home','home']);
  rows[3].observed_at=new Date(1700000000000+600000).toISOString();
  assert.equal(summarize(rows).count,1);
  rows[3].observed_at=rows[2].observed_at;
  assert.equal(summarize(rows).count,1);
  assert.equal(advance({session_id:'paper',cursor:'missing'},{session_id:'paper',events:rows}).notices[0].kind,'history_gap');
});
test('observer heartbeat alone is not proof of fresh capture',()=>{
  assert.equal(healthOf({ready:true},{observer_online:true,data_stale:true}),'capture_stale');
  assert.equal(healthOf({ready:true},{observer_online:false,data_stale:true}),'observer_offline');
  assert.equal(healthOf({ready:true},{observer_online:true,data_stale:false}),'ok');
});
