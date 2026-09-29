const fs = require('fs');

async function run() {
  const r = await fetch('https://ironman.fandom.com/wiki/Iron_Man_Mark_III', {
    headers: { 'User-Agent': 'Mozilla/5.0' }
  });
  const html = await r.text();
  const urls = [];
  const parts = html.split('https://static.wikia.nocookie.net/');
  for (let i = 1; i < parts.length; i++) {
    const end = parts[i].search(/["'\s]/);
    if (end > 0) {
      const u = 'https://static.wikia.nocookie.net/' + parts[i].slice(0, end);
      if (u.includes('.png') || u.includes('.jpg')) {
        urls.push(u.split('/revision/')[0]);
      }
    }
  }
  const unique = Array.from(new Set(urls));
  console.log('Unique images:', unique);
}

run().catch(console.error);
