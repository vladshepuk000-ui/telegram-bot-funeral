const express = require('express');
const os = require('os');

const app = express();
const PORT = 3000;

app.use(express.json());

app.get('/', (req, res) => {
  res.json({ message: 'Hello, World!' });
});

function getNetworkAddress() {
  const interfaces = os.networkInterfaces();
  for (const name of Object.keys(interfaces)) {
    for (const iface of interfaces[name]) {
      if (iface.family === 'IPv4' && !iface.internal) {
        return iface.address;
      }
    }
  }
  return 'unavailable';
}

app.listen(PORT, () => {
  console.log(`\n  Local:   http://localhost:${PORT}`);
  console.log(`  Network: http://${getNetworkAddress()}:${PORT}\n`);
});
