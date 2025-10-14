import Dexie from 'dexie';

export class FantasyDatabase extends Dexie {
  constructor() {
    super('FantasyFootballDB');
    this.version(1).stores({
      players: '++id, player_name, team, position, power_score, sleeper_rating, matchup_difficulty, risk_level',
      scraper_logs: '++id, timestamp, source, status, message',
      settings: 'key, value'
    });
  }
}

export const db = new FantasyDatabase();