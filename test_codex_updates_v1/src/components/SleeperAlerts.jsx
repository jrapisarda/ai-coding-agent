import React from 'react';
import { AlertTriangle, TrendingUp } from 'lucide-react';

function SleeperAlerts({ players }) {
  const sleepers = players.filter(player => player.sleeper_rating > 7.5).slice(0, 5);

  if (sleepers.length === 0) {
    return null;
  }

  return (
    <div className="bg-gradient-to-r from-yellow-50 to-amber-50 border-2 border-sleeper-gold rounded-lg shadow-lg p-6 mb-8">
      <div className="flex items-center space-x-2 mb-4">
        <AlertTriangle className="h-6 w-6 text-sleeper-gold" />
        <h2 className="text-xl font-bold text-gray-800">Sleeper Alerts</h2>
        <TrendingUp className="h-6 w-6 text-green-500" />
      </div>
      <div className="space-y-3">
        {sleepers.map((player) => (
          <div key={player.id} className="bg-white rounded-lg p-4 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-gray-800">{player.player_name}</h3>
                <p className="text-sm text-gray-600">{player.team} - {player.position}</p>
              </div>
              <div className="text-right">
                <div className="text-lg font-bold text-sleeper-gold">{player.sleeper_rating}</div>
                <div className="text-xs text-gray-500">Sleeper Score</div>
              </div>
            </div>
            <div className="mt-2 text-sm text-gray-700">
              <p>Power Score: {player.power_score} | Matchup: {player.matchup_difficulty}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default SleeperAlerts;