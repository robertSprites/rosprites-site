import assert from 'node:assert/strict';
// Import only the pure aggregation. No DOM or browser package is needed.
globalThis.document = { querySelector: () => null };
const { selectPeriod } = await import('../assets/analytics.js');
const snapshot = {
  generatedAt: '2026-10-26T12:00:00Z', includes: { revenue: true },
  coverage: { firstRecordedDay: '2026-10-01' },
  items: [{ key: 'a', name: '<img src=x onerror=alert(1)>', assetId: 1 }],
  daily: [
    { date: '2026-10-01', items: [{ key: 'a', sales: 2, earnedRobux: 20, website: 2 }] },
    { date: '2026-10-26', items: [{ key: 'a', sales: 1, earnedRobux: 10, inGame: 1 }] },
  ],
};
const week = selectPeriod(snapshot, '7');
assert.equal(week.days.length, 7);
assert.equal(week.start, '2026-10-20');
assert.equal(week.sales, 1);
assert.equal(week.earnedRobux, 10);
assert.deepEqual(week.location, { inGame: 1, website: 0, other: 0 });
const all = selectPeriod(snapshot, 'all');
assert.equal(all.sales, 3);
assert.equal(all.earnedRobux, 30);
assert.equal(all.days.length, 26);
assert.equal(all.items[0].name, snapshot.items[0].name);
snapshot.daily[1].items[0].earnedRobux = null;
assert.equal(selectPeriod(snapshot, 'all').earnedRobux, null);
snapshot.includes.revenue = false;
assert.equal(selectPeriod(snapshot, 'all').earnedRobux, null);
assert.equal(selectPeriod(snapshot, 'all').sales, 3);
console.log('Date filters, item totals, locations, and unknown-revenue handling passed.');
