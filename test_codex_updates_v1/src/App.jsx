import React, { useState, useEffect } from 'react';
import { Football, RefreshCw, Download } from 'lucide-react';
import PositionFilter from './components/PositionFilter';
import PlayerRankings from './components/PlayerRankings';
import SleeperAlerts from './components/SleeperAlerts';

function App() {
  const [players, setPlayers] = useState([]);
  const [selectedPosition, setSelectedPosition] = useState('all');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadInitialData();
  }, []);

  const loadInitialData = async () => {
    try {
      const response = await fetch('/api/scrape-fantasy-data');
      const data = await response.json();
      setPlayers(data.players);
    } catch (error) {
      console.error('Error loading initial data:', error);
    }
  };

  const scrapeData = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/scrape-fantasy-data');
      const data = await response.json();
      setPlayers(data.players);
    } catch (error) {
      console.error('Error scraping data:', error);
    } finally {
      setLoading(false);
    }
  };

  const exportToCSV = () => {
    const headers = ['Rank', 'Player', 'Team', 'Pos', 'Power_Score', 'Sleeper', 'Matchup', 'Risk'];
    const csvContent = [
      headers.join(','),
      ...players.map((player, index) => [
        index + 1,
        player.player_name,
        player.team,
        player.position,
        player.power_score,
        player.sleeper_rating > 7.5 ? 'Yes' : 'No',
        player.matchup_difficulty,
        player.risk_level
      ].join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'fantasy-rankings.csv';
    a.click();
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-nfl-primary text-white shadow-lg">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <Football className="h-8 w-8" />
              <h1 className="text-3xl font-bold">Fantasy Football Sleeper Scout</h1>
            </div>
            <div className="flex items-center space-x-4">
              <button
                onClick={scrapeData}
                disabled={loading}
                className="flex items-center space-x-2 bg-nfl-secondary hover:bg-red-600 px-4 py-2 rounded-lg transition-colors"
              >
                <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                <span>Refresh Data</span>
              </button>
              <button
                onClick={exportToCSV}
                className="flex items-center space-x-2 bg-green-600 hover:bg-green-700 px-4 py-2 rounded-lg transition-colors"
              >
                <Download className="h-4 w-4" />
                <span>Export CSV</span>
              </button>
            </div>
          </div>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-4 py-8">
        <SleeperAlerts players={players} />
        <PositionFilter 
          selectedPosition={selectedPosition} 
          onPositionChange={setSelectedPosition} 
        />
        <PlayerRankings 
          players={players} 
          selectedPosition={selectedPosition} 
        />
      </main>
    </div>
  );
}

export default App;