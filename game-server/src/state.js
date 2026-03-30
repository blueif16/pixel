const roomConnections = new Map();
const playerState = new Map();
const allConnections = new Map();
// TODO(persistence): roomTemplates is a temporary stand-in.
// Future: room layout lives in DynamoDB keyed by roomId (= owner's Cognito sub).
// Replace roomTemplates with a DynamoDB.get(TABLE_ROOMS, { roomId }) call that returns
// the full room document: { template, furniture[], spawnPoint, width, height }.
// On join_room, fetch from DynamoDB and send the full room doc in room_state instead of
// just the template string — client renders from that, not from a static /rooms/*.json file.
const roomTemplates = new Map(); // roomId → template id (e.g. 'cafe')

function addConnection(conn) {
  allConnections.set(conn.playerId, conn);
}

function removeConnection(conn) {
  const state = playerState.get(conn.playerId);
  if (state && state.roomId) {
    leaveRoom(conn);
  }
  allConnections.delete(conn.playerId);
}

function joinRoom(conn, roomId, x, y, avatarUrl, template) {
  if (!roomConnections.has(roomId)) {
    roomConnections.set(roomId, new Set());
  }
  roomConnections.get(roomId).add(conn);
  playerState.set(conn.playerId, {
    roomId, x, y,
    direction: 'down',
    pose: 'standing',
    seatPosition: null,
    avatarUrl,
  });
  // Only the room owner sets the template (first join or explicit template)
  if (template) roomTemplates.set(roomId, template);
}

function leaveRoom(conn) {
  const state = playerState.get(conn.playerId);
  if (!state) return null;
  const { roomId } = state;
  const roomSet = roomConnections.get(roomId);
  if (roomSet) {
    roomSet.delete(conn);
    if (roomSet.size === 0) roomConnections.delete(roomId);
  }
  playerState.delete(conn.playerId);
  return roomId;
}

function getConnectionsByRoom(roomId) {
  return roomConnections.get(roomId) || new Set();
}

function getPlayerState(playerId) {
  return playerState.get(playerId);
}

function updatePlayerState(playerId, updates) {
  const current = playerState.get(playerId);
  if (current) Object.assign(current, updates);
}

module.exports = {
  addConnection, removeConnection,
  joinRoom, leaveRoom,
  getConnectionsByRoom, getPlayerState, updatePlayerState,
  allConnections, playerState, roomConnections, roomTemplates
};
