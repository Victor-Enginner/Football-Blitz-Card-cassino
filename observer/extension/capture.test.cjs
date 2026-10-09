const {test} = require('node:test');
const assert = require('node:assert/strict');
const {createTracker, snapshot} = require('./capture.js');
test('ignore initial banner; accept stable result after a blank phase', () => {
  const tracker = createTracker(), result = {round_id:'17755021116',outcome:'home'};
  assert.equal(tracker.read(result, 0), null);
  tracker.read({...result,outcome:null}, 1);
  assert.equal(tracker.read(result, 100), null);
  assert.equal(tracker.read(result, 849), null);
  assert.deepEqual(tracker.read(result, 850), result);
});
test('identical outcome in next round is a new observation', () => {
  const tracker = createTracker();
  for (let i=0; i<4; i++) {
    const result = {round_id:String(17755021116+i), outcome:'home'};
    tracker.read({...result,outcome:null},i*2000);
    tracker.read(result,i*2000+1);
    assert.deepEqual(tracker.read(result,i*2000+1000),result);
  }
});
test('do not attach lingering winner banner to newly advanced round id', () => {
  const tracker = createTracker();
  tracker.read({round_id:'17755021116',outcome:null},0);
  tracker.read({round_id:'17755021116',outcome:'home'},1);
  assert.equal(tracker.read({round_id:'17755021117',outcome:'home'},1000),null);
  assert.equal(tracker.read({round_id:'17755021117',outcome:'home'},2000),null);
});
test('static betting labels cannot be interpreted as a result', () => {
  const doc = {body:{textContent:'Football Blitz Top Card MANDANTE EMPATE VISITANTE'},
    querySelector:()=>({textContent:'ID: 17755021116'}),querySelectorAll:()=>[]};
  assert.deepEqual(snapshot(doc),{round_id:'17755021116',outcome:null});
});
