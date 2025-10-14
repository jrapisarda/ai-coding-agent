import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api';

export const scrapeFantasyData = async () => {
  try {
    const response = await axios.get(`${API_BASE_URL}/scrape-fantasy-data`);
    return response.data.players;
  } catch (error) {
    console.error('Error scraping fantasy data:', error);
    return getMockFantasyData();
  }
};

const getMockFantasyData = () => {
  return [
    {
      id: 1,
      player_name: 'Christian McCaffrey',
      team: 'SF',
      position: 'RB',
      power_score: 94.2,
      performance_score: 96.1,
      projection_score: 92.3,
      sleeper_rating: 3.2,
      last_4_week_avg: 24.5,
      next_opponent: 'SEA',
      matchup_difficulty: 'Favorable',
      expert_consensus_rank: 1,
      value_gap: 0,
      risk_level: 'Low',
      recommendation: 'Must Start'
    },
    {
      id: 2,
      player_name: 'Tyreek Hill',
      team: 'MIA',
      position: 'WR',
      power_score: 91.8,
      performance_score: 93.4,
      projection_score: 90.2,
      sleeper_rating: 4.1,
      last_4_week_avg: 21.8,
      next_opponent: 'NYJ',
      matchup_difficulty: 'Neutral',
      expert_consensus_rank: 3,
      value_gap: 1,
      risk_level: 'Low',
      recommendation: 'Must Start'
    },
    {
      id: 3,
      player_name: 'Jaylen Warren',
      team: 'PIT',
      position: 'RB',
      power_score: 78.5,
      performance_score: 75.2,
      projection_score: 81.8,
      sleeper_rating: 8.9,
      last_4_week_avg: 14.2,
      next_opponent: 'CLE',
      matchup_difficulty: 'Neutral',
      expert_consensus_rank: 28,
      value_gap: 15,
      risk_level: 'Medium',
      recommendation: 'Strong Sleeper'
    },
    {
      id: 4,
      player_name: 'Tyjae Spears',
      team: 'TEN',
      position: 'RB',
      power_score: 72.1,
      performance_score: 68.9,
      projection_score: 75.3,
      sleeper_rating: 9.2,
      last_4_week_avg: 11.8,
      next_opponent: 'IND',
      matchup_difficulty: 'Favorable',
      expert_consensus_rank: 45,
      value_gap: 20,
      risk_level: 'High',
      recommendation: 'Deep Sleeper'
    },
    {
      id: 5,
      player_name: 'Patrick Mahomes',
      team: 'KC',
      position: 'QB',
      power_score: 89.3,
      performance_score: 88.7,
      projection_score: 90.1,
      sleeper_rating: 2.8,
      last_4_week_avg: 22.1,
      next_opponent: 'LV',
      matchup_difficulty: 'Favorable',
      expert_consensus_rank: 2,
      value_gap: 0,
      risk_level: 'Low',
      recommendation: 'Must Start'
    }
  ];
};