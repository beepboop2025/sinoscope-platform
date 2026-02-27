# DragonScope Enterprise

A Bloomberg-grade professional trading terminal interface built with React 18, Zustand, and Lightweight Charts.

![DragonScope Enterprise](https://img.shields.io/badge/DragonScope-Enterprise-blue)
![React](https://img.shields.io/badge/React-18.2-61DAFB?logo=react)
![Vite](https://img.shields.io/badge/Vite-5.0-646CFF?logo=vite)
![TailwindCSS](https://img.shields.io/badge/Tailwind-3.4-06B6D4?logo=tailwindcss)

## Features

### 🖥️ Terminal Layout
- **Multi-panel layout** - View 4+ panels simultaneously
- **Detachable panels** - Pop out panels for multi-monitor support
- **Tabbed interface** - Multiple tabs within each panel
- **Collapsible sidebar** - Maximize screen real estate
- **Command palette** (Cmd+K) - VS Code-style quick actions

### 📊 PriceChart Pro
- **Multiple chart types**: Candlestick, Line, Area, Bar, Heikin-Ashi
- **Technical indicators**: SMA, EMA, Bollinger Bands, RSI, MACD, Volume
- **Drawing tools**: Trendlines, Fibonacci, Support/Resistance
- **Multiple timeframes**: 1m, 5m, 15m, 1h, 4h, D, W, M
- **Symbol comparison** - Overlay multiple symbols
- **Crosshair tracking** with data readout

### 📖 Order Book
- **Level 2 market depth** visualization
- **Bid/ask ladder** with size bars
- **Trade tape** / Time & Sales
- **Market depth heatmap**
- **Cumulative volume profile**
- Real-time updates simulation

### 📈 Watchlist Pro
- **Sortable/filterable** watchlist
- **Real-time price updates** via WebSocket simulation
- **Custom columns**: Price, Change, Volume, Spread, RSI, etc.
- **Heat map mode** - Visual price change representation
- **Quick trade buttons** - Buy/Sell directly from watchlist
- Grid and list view modes

### 📰 News Feed
- **Real-time news ticker**
- **Sentiment indicators** (Bullish/Bearish/Neutral)
- **Keyword highlighting**
- **Filter by**: Symbol, Sector, Source, Sentiment
- **Breaking news** alerts
- Price impact correlation

## Tech Stack

- **React 18** - Modern React with hooks
- **Zustand** - Lightweight state management with Immer
- **Tailwind CSS** - Utility-first styling
- **Lightweight Charts** - Professional financial charting
- **Lucide React** - Beautiful icons
- **Vite** - Fast development and building

## Getting Started

### Prerequisites

- Node.js 18+ 
- npm or yarn

### Installation

```bash
# Clone the repository
git clone https://github.com/dragonscope/enterprise.git
cd enterprise/frontend-pro

# Install dependencies
npm install

# Start development server
npm run dev
```

The application will be available at `http://localhost:3000`

### Building for Production

```bash
npm run build
```

The built files will be in the `dist/` directory.

## Project Structure

```
frontend-pro/
├── public/                  # Static assets
├── src/
│   ├── components/          # React components
│   │   ├── TerminalLayout.jsx    # Main terminal layout
│   │   ├── PriceChartPro.jsx     # Professional chart component
│   │   ├── OrderBook.jsx         # L2 market depth
│   │   ├── WatchlistPro.jsx      # Advanced watchlist
│   │   └── NewsFeed.jsx          # Real-time news feed
│   ├── stores/              # Zustand state stores
│   │   └── terminalStore.js      # Main terminal state
│   ├── hooks/               # Custom React hooks
│   │   └── useWebSocket.js       # WebSocket management
│   ├── utils/               # Utility functions
│   │   └── styles.js             # Formatting and calculations
│   ├── styles/              # CSS styles
│   │   └── index.css             # Tailwind + custom styles
│   ├── App.jsx              # Main application
│   └── main.jsx             # Entry point
├── index.html
├── package.json
├── tailwind.config.js
├── postcss.config.js
└── vite.config.js
```

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Cmd/Ctrl + K` | Open Command Palette |
| `Cmd/Ctrl + B` | Toggle Sidebar |
| `Escape` | Close Modals/Panels |
| `Arrow Keys` | Navigate in Command Palette |
| `Enter` | Select in Command Palette |

## Configuration

### State Persistence

The terminal layout and settings are automatically persisted to localStorage. Customize the persistence behavior in `terminalStore.js`.

### WebSocket Connections

WebSocket endpoints can be configured in `useWebSocket.js`. The app includes hooks for:
- Market data streaming
- Order book updates
- News feeds

### Chart Defaults

Default chart settings (timeframe, indicators, etc.) can be modified in the store configuration.

## Customization

### Adding New Panel Types

1. Create your component in `src/components/`
2. Register it in `TerminalLayout.jsx` render function
3. Add to Command Palette commands

### Adding Indicators

New technical indicators can be added to:
1. `INDICATORS` array in `PriceChartPro.jsx`
2. Calculation functions in `utils/styles.js`
3. Chart series creation in `PriceChartPro.jsx`

## Browser Support

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## Performance Considerations

- Charts use `ResizeObserver` for efficient resizing
- State updates use Immer for immutable updates
- WebSocket connections auto-reconnect
- Virtual scrolling for long lists (news, trades)
- Debounced search inputs

## License

MIT License - see LICENSE file for details

## Contributing

Contributions welcome! Please read our Contributing Guide.

---

Built with ❤️ by the DragonScope Team
