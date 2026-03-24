const { generateAvatar } = require('../avatar');
const { buildCharacterDescription } = require('../prompt');
const { sendTo } = require('../broadcast');
const socialEngine = require('../modules/socialEngine');

async function handleCreateCharacter(conn, payload) {
  const { hairStyle, hairColor, skinTone, outfit, outfitColor, accessory } = payload;

  const description = buildCharacterDescription({
    hairStyle, hairColor, skinTone, outfit, outfitColor, accessory
  });

  sendTo(conn, { type: 'character_generating', payload: { message: 'Creating your character...' } });

  const avatarUrl = await generateAvatar(conn.playerId, description);

  await socialEngine.createPlayer(conn.playerId, conn.displayName, avatarUrl);

  sendTo(conn, { type: 'character_created', payload: { avatarUrl } });
}

module.exports = { handleCreateCharacter };
