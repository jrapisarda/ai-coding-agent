export const calculatePowerScores = (players) => {
  return players.map(player => {
    const performanceWeight = 0.4;
    const projectionWeight = 0.35;
    const sleeperWeight = 0.25;
    
    const normalizedPerformance = normalizeScore(player.performance_score, 0, 100);
    const normalizedProjection = normalizeScore(player.projection_score, 0, 100);
    const normalizedSleeper = normalizeScore(player.sleeper_rating, 0, 10);
    
    const powerScore = (
      normalizedPerformance * performanceWeight +
      normalizedProjection * projectionWeight +
      normalizedSleeper * sleeperWeight * 10
    );
    
    return {
      ...player,
      power_score: Math.round(powerScore * 10) / 10
    };
  }).sort((a, b) => b.power_score - a.power_score);
};

const normalizeScore = (score, min, max) => {
  return Math.max(0, Math.min(100, ((score - min) / (max - min)) * 100));
};

export const identifySleepers = (players) => {
  return players.filter(player => {
    return player.sleeper_rating > 7.5 &&
           player.expert_consensus_rank - player.power_score > 10 &&
           player.risk_level !== 'High';
  });
};

export const analyzeTrends = (playerData) => {
  const recentGames = playerData.slice(-4);
  const trendScore = recentGames.reduce((acc, game, index) => {
    const weight = index + 1;
    return acc + (game.points * weight);
  }, 0) / recentGames.length;
  
  return {
    trend_direction: trendScore > playerData.slice(-8, -4).reduce((acc, game) => acc + game.points, 0) / 4 ? 'Up' : 'Down',
    trend_score: Math.round(trendScore * 10) / 10
  };
};