// decorEngine.js — stub for B's furniture/decor module
// See docs/integration-guide-B-C.md for full spec

async function getRoomFurniture(roomId) {
  // TODO(B): query DynamoDB TABLE_INTERACTIONS for FURNITURE# records
  return [];
}

async function placeFurniture(conn, payload) {
  throw new Error('decorEngine.placeFurniture: not yet implemented');
}

async function moveFurniture(conn, payload) {
  throw new Error('decorEngine.moveFurniture: not yet implemented');
}

async function rotateFurniture(conn, payload) {
  throw new Error('decorEngine.rotateFurniture: not yet implemented');
}

async function removeFurniture(conn, payload) {
  throw new Error('decorEngine.removeFurniture: not yet implemented');
}

async function isWalkable(roomId, x, y) {
  // TODO(B): check if tile is occupied by furniture
  return true;
}

module.exports = {
  getRoomFurniture,
  placeFurniture, moveFurniture, rotateFurniture, removeFurniture,
  isWalkable,
};
