const http = require('http');
const { WebSocketServer } = require('ws');
const { validateToken } = require('./auth');
const { handleMessage } = require('./router');
const { addConnection, removeConnection } = require('./state');

const server = http.createServer((req, res) => {
  if (req.url === '/health') {
    res.writeHead(200);
    res.end('ok');
    return;
  }
  res.writeHead(404);
  res.end();
});

const wss = new WebSocketServer({ server, path: '/ws' });

wss.on('connection', async (ws, req) => {
  const url = new URL(req.url, `http://${req.headers.host}`);
  const token = url.searchParams.get('token');

  let user;
  try {
    user = await validateToken(token);
  } catch (err) {
    ws.close(4001, 'Invalid token');
    return;
  }

  const conn = { ws, playerId: user.sub, displayName: user.preferred_username };
  addConnection(conn);

  ws.on('message', (raw) => {
    try {
      const msg = JSON.parse(raw);
      handleMessage(conn, msg);
    } catch (err) {
      ws.send(JSON.stringify({ type: 'error', payload: { code: 'PARSE_ERROR', message: 'Invalid JSON' } }));
    }
  });

  ws.on('close', () => {
    removeConnection(conn);
  });
});

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => console.log(`Game server on :${PORT}`));
