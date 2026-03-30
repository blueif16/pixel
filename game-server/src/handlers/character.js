const { generateAvatar } = require('../avatar');
const { buildCharacterDescription } = require('../prompt');
const { sendTo } = require('../broadcast');
const socialEngine = require('../modules/socialEngine');

async function handleCreateCharacter(conn, payload) {
  // Accept direct description text (simple mode) or structured fields (legacy)
  let description = payload.description;
  if (!description) {
    const { hairStyle, hairColor, skinTone, outfit, outfitColor, accessory } = payload;
    description = buildCharacterDescription({ hairStyle, hairColor, skinTone, outfit, outfitColor, accessory });
  }
  // Sanitize: cap at 200 chars, wrap with guardrails
  description = `A young person, ${description.slice(0, 200)}`;

  sendTo(conn, { type: 'character_generating', payload: { message: 'Creating your character...' } });

  const avatarUrl = await generateAvatar(conn.playerId, description);

  await socialEngine.createPlayer(conn.playerId, conn.displayName, avatarUrl);

  sendTo(conn, { type: 'character_created', payload: { avatarUrl, playerId: conn.playerId } });
}

module.exports = { handleCreateCharacter };
