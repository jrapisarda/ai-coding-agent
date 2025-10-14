import React from 'react';

const positions = [
  { value: 'all', label: 'All Positions' },
  { value: 'QB', label: 'Quarterbacks' },
  { value: 'RB', label: 'Running Backs' },
  { value: 'WR', label: 'Wide Receivers' },
  { value: 'TE', label: 'Tight Ends' }
];

function PositionFilter({ selectedPosition, onPositionChange }) {
  return (
    <div className="flex space-x-2 mb-6">
      {positions.map((position) => (
        <button
          key={position.value}
          onClick={() => onPositionChange(position.value)}
          className={`px-4 py-2 rounded-lg font-medium transition-colors ${
            selectedPosition === position.value
              ? 'bg-nfl-primary text-white'
              : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
          }`}
        >
          {position.label}
        </button>
      ))}
    </div>
  );
}

export default PositionFilter;