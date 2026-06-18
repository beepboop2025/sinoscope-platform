# DragonScope Enterprise - User Guide

Complete guide for traders, analysts, and portfolio managers using DragonScope Enterprise.

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Terminal Layout](#terminal-layout)
3. [Panels & Components](#panels--components)
4. [Keyboard Shortcuts](#keyboard-shortcuts)
5. [Workspace Customization](#workspace-customization)
6. [Alerts & Watchlists](#alerts-and-watchlists)
7. [Charting & Analysis](#charting--analysis)
8. [Order Management](#order-management)
9. [Risk Management](#risk-management)

---

## Getting Started

### First Launch

When you start DragonScope Enterprise for the first time:

```
┌─────────────────────────────────────────────────────────────────┐
│  🐉 Welcome to DragonScope Enterprise                            │
│                                                                  │
│  Let's set up your trading environment:                          │
│                                                                  │
│  1. Choose your profile type:                                    │
│     ○ Day Trader          ○ Swing Trader                        │
│     ○ Portfolio Manager   ○ Quantitative Analyst                │
│     ○ Risk Manager        ○ Custom                              │
│                                                                  │
│  2. Connect your broker (optional):                              │
│     [Select Broker...] ▼                                        │
│                                                                  │
│  3. Import watchlists:                                           │
│     [Upload CSV]  or  [Start Fresh]                              │
│                                                                  │
│              [  Get Started  ]                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Quick Tour (2 Minutes)

Press `F1` or go to **Help → Interactive Tour** for a guided walkthrough.

### Essential Setup Checklist

- [ ] Configure market data subscriptions
- [ ] Connect brokerage account(s)
- [ ] Set up risk limits and alerts
- [ ] Customize default workspace
- [ ] Configure notification preferences
- [ ] Set up backup/restore options

---

## Terminal Layout

DragonScope uses a flexible, dockable panel system inspired by professional trading terminals.

### Default Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Menu Bar │ File  View  Panels  Analysis  Trading  Tools  Help              │
├─────────────────────────────────────────────────────────────────────────────┤
│ Toolbar  │ [New] [Save] [Layout▼] [Symbol: AAPL    ] [🔍] [⏯️ Live]        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐  ┌──────────────────────────────┐  ┌──────────────┐   │
│  │              │  │                              │  │              │   │
│  │   WATCHLIST  │  │                              │  │   ORDER      │   │
│  │   ┌────────┐ │  │      CHART (Main)            │  │   BOOK       │   │
│  │   │ AAPL   │ │  │      ┌────────────────┐      │  │   ┌────────┐ │   │
│  │   │ MSFT   │ │  │      │                │      │  │   │ Bid 150│ │   │
│  │   │ GOOGL  │ │  │      │    [Candle]    │      │  │   │ Ask 151│ │   │
│  │   │ ...    │ │  │      │                │      │  │   │ ...    │ │   │
│  │   └────────┘ │  │      └────────────────┘      │  │   └────────┘ │   │
│  │              │  │                              │  │              │   │
│  │              │  │  Time: 1D  1W  1M  3M  1Y    │  │              │   │
│  └──────────────┘  └──────────────────────────────┘  └──────────────┘   │
│                                                                          │
│  ┌──────────────────────────┐  ┌────────────────────────────────────┐   │
│  │                          │  │                                    │   │
│  │   PORTFOLIO / POSITIONS  │  │   NEWS & RESEARCH                  │   │
│  │   ┌────────────────┐    │  │   ┌────────────────────────────┐   │   │
│  │   │ Symbol │ Qty   │    │  │   │ 🔔 AAPL: Earnings beat...  │   │   │
│  │   │ AAPL   │ 100   │    │  │   │ 📰 Fed signals rate cut... │   │   │
│  │   │ TSLA   │ -50   │    │  │   │ 📊 MSFT upgrade to Buy     │   │   │
│  │   │ ...    │ ...   │    │  │   │ ...                        │   │   │
│  │   └────────────────┘    │  │   └────────────────────────────┘   │   │
│  │   P&L: +$2,450 (+1.2%)  │  │                                    │   │
│  └──────────────────────────┘  └────────────────────────────────────┘   │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│ Status   │ Connected │ Latency: 12ms │ Memory: 450MB │ CPU: 23% │ 14:32:05 │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Layout Zones

| Zone | Description | Default Content |
|------|-------------|-----------------|
| **Left Sidebar** | Navigation & lists | Watchlists, quotes |
| **Center** | Primary focus area | Charts, scanners |
| **Right Sidebar** | Contextual data | Order book, Level 2 |
| **Bottom** | Monitoring & research | Portfolio, news, alerts |
| **Top** | Global controls | Toolbar, symbol entry |

---

## Panels & Components

### Quote Panel

Real-time quote display with configurable fields.

```
┌─────────────────────────────┐
│  AAPL - Apple Inc.          │
│  NASDAQ | Tech | Large Cap  │
├─────────────────────────────┤
│  Last:    185.92  ▲ +2.34   │
│  Bid:     185.90  x 500     │
│  Ask:     185.95  x 300     │
│  Size:    12.5M             │
│  Vol:     45.2M / 52M avg   │
│  Open:    183.50            │
│  High:    186.10            │
│  Low:     182.75            │
│  Close:   183.58            │
│  52W:   165.00 - 199.62     │
│  Mkt Cap: $2.89T            │
│  P/E:     28.5              │
├─────────────────────────────┤
│  [Buy] [Sell] [Chart] [⚙️]  │
└─────────────────────────────┘
```

**Configuration Options:**
- Field selection (50+ data points)
- Color schemes
- Decimal precision
- Auto-refresh intervals

### Chart Panel

Professional-grade charting with multiple chart types.

```
┌─────────────────────────────────────────────────────────────┐
│ AAPL - Daily                                    [⚙️] [🔍]  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│    200 ┤                                          ╭─╮      │
│        │                                    ╭────╯  ╰──╮   │
│    190 ┤      ╭──╮                    ╭────╯            ╰──│
│        │ ╭────╯  ╰──╮            ╭────╯                   │
│    180 ┤─╯          ╰────────────╯                         │
│        │                                                    │
│    170 ┤                                                    │
│        └────┬────┬────┬────┬────┬────┬────┬────┬────      │
│           Jan  Feb  Mar  Apr  May  Jun  Jul  Aug           │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  [Candle] [Bar] [Line] [Heikin] [Renko] [Kagi]              │
│  1m  5m  15m  30m  1H  4H  1D  1W  1M  [Custom]             │
│  [Indicators▼] [Studies▼] [Drawings▼] [Alert▼]              │
└─────────────────────────────────────────────────────────────┘
```

**Supported Chart Types:**
- Candlestick (OHLC)
- Bar (OHLC)
- Line
- Area
- Heikin-Ashi
- Renko
- Kagi
- Point & Figure
- Range Bars
- Tick Charts

### Order Book Panel

Real-time Level 2 market depth.

```
┌─────────────────────┐
│  AAPL Order Book    │
├─────────┬───────────┤
│  Ask    │   Size    │
├─────────┼───────────┤
│ 185.98  │    1,200  │ ← Large offer
│ 185.97  │      300  │
│ 185.96  │      800  │
│ 185.95  │      500  │ ← Inside ask
├─────────┴───────────┤
│    SPREAD: 0.05     │
├─────────┬───────────┤
│ 185.90  │      500  │ ← Inside bid
│ 185.89  │      250  │
│ 185.88  │    1,500  │
│ 185.87  │      400  │
├─────────┴───────────┤
│ [L2] [L3] [Time&Sales]│
└─────────────────────┘
```

### Portfolio Panel

Complete position and P&L tracking.

```
┌─────────────────────────────────────────────────────────┐
│  Portfolio Summary                              [⚙️]   │
├─────────────────────────────────────────────────────────┤
│  Total Value:    $1,245,678.90                          │
│  Day P&L:        +$12,450 (+1.02%)  🟢                   │
│  Total P&L:      +$45,230 (+3.77%)  🟢                   │
│  Buying Power:   $354,321.10                            │
│  Margin Used:    28.5%                                  │
├──────────┬────────┬─────────┬──────────┬────────┬───────┤
│ Symbol   │ Qty    │ AvgCost │ Last     │ P&L    │ %     │
├──────────┼────────┼─────────┼──────────┼────────┼───────┤
│ AAPL     │ 100    │ 180.50  │ 185.92   │ +542   │ +3.0% │
│ MSFT     │ 50     │ 370.00  │ 385.20   │ +760   │ +4.1% │
│ TSLA     │ -25    │ 245.00  │ 238.50   │ +162   │ +2.7% │
│ NVDA     │ 30     │ 420.00  │ 445.80   │ +774   │ +6.1% │
│ SPY      │ 200    │ 445.00  │ 448.20   │ +640   │ +0.7% │
└──────────┴────────┴─────────┴──────────┴────────┴───────┘
```

### News Panel

Curated news and research integration.

```
┌─────────────────────────────────────┐
│  News & Research            [🔍]   │
├─────────────────────────────────────┤
│  Filters: [All▼] [Sources▼] [🔔]   │
├─────────────────────────────────────┤
│  🔔 14:32  AAPL                     │
│  Earnings beat: $2.18 vs $2.10 exp │
│  Source: Bloomberg                  │
│                                     │
│  📰 14:15  Market                   │
│  Fed signals potential rate cuts... │
│  Source: Reuters                    │
│                                     │
│  📊 13:45  MSFT                     │
│  Morgan Stanley upgrades to Buy     │
│  PT raised to $450                  │
│  Source: The Fly                    │
├─────────────────────────────────────┤
│  [Markets] [Stocks] [Options]       │
└─────────────────────────────────────┘
```

---

## Keyboard Shortcuts

### Global Shortcuts

| Shortcut | Action | Context |
|----------|--------|---------|
| `Ctrl/Cmd + T` | New tab | Global |
| `Ctrl/Cmd + W` | Close tab/panel | Global |
| `Ctrl/Cmd + Shift + T` | Reopen closed tab | Global |
| `Ctrl/Cmd + F` | Find symbol | Global |
| `Ctrl/Cmd + K` | Command palette | Global |
| `Ctrl/Cmd + ,` | Preferences | Global |
| `F1` | Help / Interactive Tour | Global |
| `F11` | Fullscreen | Global |
| `Escape` | Cancel / Close dialog | Global |

### Trading Shortcuts

| Shortcut | Action | Context |
|----------|--------|---------|
| `B` | Buy order ticket | Global |
| `S` | Sell order ticket | Global |
| `C` | Cover order ticket | Global |
| `Shift + S` | Short sell order | Global |
| `Enter` | Submit order | Order ticket |
| `Escape` | Cancel order | Order ticket |
| `F9` | Quick buy (market) | Global |
| `F10` | Quick sell (market) | Global |
| `F12` | Flatten all positions | Global |
| `Ctrl/Cmd + 1-9` | Switch workspace | Global |

### Navigation Shortcuts

| Shortcut | Action | Context |
|----------|--------|---------|
| `Tab` | Next panel | Global |
| `Shift + Tab` | Previous panel | Global |
| `Ctrl/Cmd + Arrow` | Move between panels | Global |
| `Alt + 1-9` | Switch to tab N | Global |
| `Ctrl/Cmd + R` | Refresh current panel | Global |
| `Ctrl/Cmd + Shift + R` | Hard refresh | Global |
| `Space` | Play/Pause data stream | Chart |
| `+` / `-` | Zoom in/out | Chart |
| `Home` | Go to latest candle | Chart |
| `End` | Go to oldest candle | Chart |
| `Arrow Keys` | Navigate chart | Chart |
| `Shift + Arrow` | Scroll faster | Chart |

### Chart Shortcuts

| Shortcut | Action | Context |
|----------|--------|---------|
| `1-9` | Change timeframe | Chart |
| `D` | Daily timeframe | Chart |
| `W` | Weekly timeframe | Chart |
| `M` | Monthly timeframe | Chart |
| `I` | Toggle indicators | Chart |
| `V` | Toggle volume | Chart |
| `C` | Toggle crosshair | Chart |
| `F` | Toggle fullscreen chart | Chart |
| `S` | Screenshot chart | Chart |
| `Ctrl/Cmd + S` | Save chart template | Chart |
| `Ctrl/Cmd + Z` | Undo drawing | Chart |
| `Ctrl/Cmd + Shift + Z` | Redo drawing | Chart |

### Panel-Specific Shortcuts

**Watchlist Panel:**
| Shortcut | Action |
|----------|--------|
| `↑` / `↓` | Navigate symbols |
| `Enter` | Open in chart |
| `Delete` | Remove from watchlist |
| `F2` | Rename watchlist |
| `Ctrl/Cmd + A` | Add symbol |
| `Ctrl/Cmd + E` | Export watchlist |

**Order Book Panel:**
| Shortcut | Action |
|----------|--------|
| `Shift + Click` | Buy at clicked price |
| `Ctrl + Click` | Sell at clicked price |
| `B` | Show only bids |
| `A` | Show only asks |
| `T` | Toggle Time & Sales |

---

## Workspace Customization

### Creating Custom Workspaces

DragonScope supports multiple workspace layouts for different trading strategies.

**Preset Workspaces:**

| Workspace | Best For | Panels |
|-----------|----------|--------|
| **Day Trading** | Active intraday trading | 4 charts, L2, T&S, scanner |
| **Swing Trading** | Multi-day positions | Chart, watchlist, news, fundamentals |
| **Portfolio** | Long-term management | Positions, risk, sector allocation |
| **Options** | Options trading | Options chain, Greeks, risk graph |
| **Research** | Fundamental analysis | Financials, news, earnings calendar |
| **Crypto** | Cryptocurrency trading | Multi-exchange, order book, depth |

### Creating a Custom Workspace

1. **Arrange Panels**
   ```
   Drag panel headers to:
   - Dock left/right/top/bottom
   - Tab multiple panels together
   - Float as separate window
   - Create split views
   ```

2. **Save Layout**
   ```
   Layout → Save Workspace As → Enter name
   ```

3. **Set Default**
   ```
   Layout → Set as Default
   ```

### Panel Configuration

Each panel can be customized via the gear icon (⚙️):

```
┌─────────────────────────────────────────┐
│  Panel Settings                         │
├─────────────────────────────────────────┤
│                                         │
│  📐 Layout                              │
│    Size: [Small ▼]                      │
│    Font: [System ▼]                     │
│    Theme: [Dark ▼]                      │
│                                         │
│  📊 Data                                │
│    Refresh: [Real-time ▼]               │
│    Buffer: [1000 ▼] rows                │
│                                         │
│  🔔 Alerts                              │
│    [✓] Price alerts                     │
│    [✓] Volume alerts                    │
│    [ ] News alerts                      │
│                                         │
│  📤 Export                              │
│    [Configure...]                       │
│                                         │
│         [Cancel]  [  Save  ]            │
└─────────────────────────────────────────┘
```

### Symbol Linking

Link panels to synchronize symbol changes:

```
┌───────────────────────────────────────────────────────────┐
│  Symbol Link Groups                                       │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  🔴 Red Link Group:                                       │
│     [Chart-1] [Quote-1] [News-1]                         │
│                                                           │
│  🟢 Green Link Group:                                     │
│     [Chart-2] [L2-2] [Order-2]                           │
│                                                           │
│  🔵 Blue Link Group:                                      │
│     [Chart-3] [Options-1]                                │
│                                                           │
│  ⚪ No Link (Independent):                                │
│     [Scanner] [Watchlist-Main]                           │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

**To link panels:**
1. Right-click panel header
2. Select **Link To → [Color]**
3. Changing symbol in one panel updates all linked panels

---

## Alerts and Watchlists

### Creating Watchlists

**Method 1: Manual Creation**
```
Watchlist Panel → Right-click → New Watchlist
```

**Method 2: Import from CSV**
```csv
symbol,name,sector,notes
AAPL,Apple Inc.,Technology,Core holding
MSFT,Microsoft Corp,Technology,Dividend stock
GOOGL,Alphabet Inc,Technology,Watch for breakout
JPM,JPMorgan Chase,Financials,Earnings play
```

**Method 3: Dynamic Watchlist (Screener)**
```
New Watchlist → Dynamic → Set Criteria:
  - Market Cap > $10B
  - P/E < 20
  - Dividend Yield > 2%
  - Volume > 1M
```

### Watchlist Management

```
┌───────────────────────────────────────────┐
│  My Watchlists                    [+]    │
├───────────────────────────────────────────┤
│  📁 Tech Leaders (12)              ▼     │
│  📁 Dividend Stocks (25)           ▼     │
│  📁 Earnings Plays (8)             ▼     │
│  📁 Crypto (15)                    ▼     │
│  📊 Screener: High Volume          ▶     │
│  📊 Screener: Breakouts            ▶     │
├───────────────────────────────────────────┤
│  [Import] [Export] [Share]               │
└───────────────────────────────────────────┘
```

### Setting Up Alerts

**Price Alerts:**
```
1. Right-click on symbol → Set Alert
2. Or use Alert Panel → New Alert
3. Configure:
   - Trigger: Price crosses above/below
   - Value: $185.00
   - Expiration: GTC / 30 days
   - Notification: Desktop + Email + SMS
```

**Alert Types:**

| Alert Type | Description | Example |
|------------|-------------|---------|
| **Price** | Price threshold | AAPL > $200 |
| **Volume** | Volume spike | Volume > 2x average |
| **News** | News keyword | Contains "FDA approval" |
| **Technical** | Indicator signal | RSI < 30 |
| **Fundamental** | Earnings/data | EPS beat estimate |
| **Custom** | Formula-based | Price > VWAP + 2% |

**Alert Panel Layout:**

```
┌───────────────────────────────────────────────────────────┐
│  Active Alerts                                   [+]     │
├───────────────────────────────────────────────────────────┤
│  Filters: [All▼] [Active▼] [Asset▼]                      │
├───────────────────────────────────────────────────────────┤
│  Status │ Symbol │ Alert Type       │ Trigger    │ Expires│
├─────────┼────────┼──────────────────┼────────────┼────────┤
│  🟢     │ AAPL   │ Price > 200      │ $185.92    │ GTC    │
│  🟢     │ TSLA   │ Volume Spike     │ 45M/20M    │ 7 days │
│  🟡     │ NVDA   │ RSI Oversold     │ RSI: 28.5  │ GTC    │
│  🔴     │ MSFT   │ Price < 350      │ TRIGGERED  │ -      │
├───────────────────────────────────────────────────────────┤
│  [Ack All] [Export] [History]                            │
└───────────────────────────────────────────────────────────┘
```

### Advanced Alert Conditions

**Multi-Condition Alerts:**
```javascript
// DragonScope Alert Script (DAS)
alert {
  symbol: "AAPL",
  conditions: [
    price > sma(20) AND
    volume > volume_sma(20) * 1.5 AND
    rsi(14) < 70
  ],
  timeframe: "5m",
  notification: {
    desktop: true,
    email: "trader@firm.com",
    webhook: "https://api.trading.com/alerts"
  }
}
```

**Webhook Integration:**
```bash
# Alert webhook payload
{
  "alert_id": "alert_12345",
  "symbol": "AAPL",
  "trigger_type": "price_above",
  "trigger_value": 200.00,
  "current_price": 200.50,
  "timestamp": "2026-01-15T14:30:00Z",
  "user_id": "user_67890"
}
```

### Alert Delivery Methods

| Method | Latency | Best For |
|--------|---------|----------|
| **In-App** | <10ms | Active trading |
| **Desktop** | <100ms | Background monitoring |
| **Email** | 1-5 min | Daily summaries |
| **SMS** | 5-30 sec | Critical alerts |
| **Webhook** | <1 sec | Automated trading |
| **Slack** | 1-3 sec | Team coordination |
| **Push** | <1 sec | Mobile app users |

---

## Charting & Analysis

### Technical Indicators

**Trend Indicators:**
- Moving Averages (SMA, EMA, WMA, VWAP)
- Bollinger Bands
- Ichimoku Cloud
- Parabolic SAR
- SuperTrend

**Momentum Indicators:**
- RSI (Relative Strength Index)
- MACD
- Stochastic
- CCI
- Williams %R

**Volume Indicators:**
- Volume Profile
- OBV (On Balance Volume)
- VWAP
- Chaikin Money Flow
- Klinger Volume Oscillator

**Volatility Indicators:**
- ATR (Average True Range)
- Bollinger Bands %B
- Keltner Channels
- Donchian Channels

### Drawing Tools

| Tool | Shortcut | Description |
|------|----------|-------------|
| Trend Line | `T` | Connect two points |
| Horizontal Line | `H` | Support/resistance |
| Vertical Line | `V` | Time markers |
| Fibonacci | `F` | Retracements/extensions |
| Rectangle | `R` | Price zones |
| Circle | `C` | Key areas |
| Text | `X` | Annotations |
| Measure | `M` | Price/time distance |
| Gann Fan | `G` | Geometric angles |
| Pitchfork | `P` | Andrews Pitchfork |

---

## Order Management

### Order Types

| Type | Description | Use Case |
|------|-------------|----------|
| **Market** | Execute at best price | Immediate fill |
| **Limit** | Execute at specified price or better | Price control |
| **Stop** | Market order when trigger hit | Stop loss |
| **Stop Limit** | Limit order when trigger hit | Precise stops |
| **Trailing Stop** | Dynamic stop based on offset | Let winners run |
| **OCO** | One-Cancels-Other | Bracket orders |
| **Bracket** | Entry + Stop + Target | Defined R/R |
| **Iceberg** | Hide order size | Large orders |
| **TWAP** | Time-weighted execution | Low impact |
| **VWAP** | Volume-weighted execution | Benchmark |

### Order Ticket

```
┌─────────────────────────────────────────┐
│  Order Ticket - AAPL                    │
├─────────────────────────────────────────┤
│                                         │
│  Symbol: [AAPL              ]          │
│  Side:   [Buy ▼]   Qty: [100    ]      │
│                                         │
│  Order Type: [Limit ▼]                 │
│  Limit Price: [185.50       ]          │
│                                         │
│  Time in Force: [Day ▼]                │
│                                         │
│  [ ] OCO (Bracket)                     │
│      Stop Loss:  [_______]             │
│      Take Profit: [_______]            │
│                                         │
│  [ ] Iceberg (Show: [100 ] of 1000)    │
│                                         │
│  Est. Value: $18,550.00                │
│  Buying Power After: $335,771.10       │
│                                         │
│        [Cancel]    [  Preview  ]       │
│                   [Submit Order]       │
└─────────────────────────────────────────┘
```

---

## Risk Management

### Position Limits

```
┌─────────────────────────────────────────────────────────┐
│  Risk Settings                                          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Position Limits:                                       │
│    Max Position Size:     [10%    ] of portfolio       │
│    Max Sector Exposure:   [25%    ]                    │
│    Max Single Trade:      [$50,000 ]                   │
│                                                         │
│  Daily Limits:                                          │
│    Max Day Loss:          [$5,000  ]                   │
│    Max Day Trades:        [20      ]                   │
│                                                         │
│  Risk Metrics:                                          │
│    [✓] Real-time VaR calculation                       │
│    [✓] Beta-adjusted exposure                          │
│    [✓] Correlation monitoring                          │
│    [ ] Auto-flatten on breach                          │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Risk Dashboard

```
┌─────────────────────────────────────────────────────────────┐
│  Risk Dashboard                                         [⚙️]│
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Portfolio Metrics              Sector Exposure             │
│  ┌────────────────────┐        ┌────────────────────┐      │
│  │ Delta:      $12.5K │        │ Tech:  ████████ 35%│      │
│  │ Gamma:      $2.3K  │        │ Fin:   ██████   25%│      │
│  │ Theta:     -$450   │        │ Health: ████    15%│      │
│  │ Vega:       $890   │        │ Other:  █████   25%│      │
│  │ VaR (95%):  $3.2K  │        └────────────────────┘      │
│  └────────────────────┘                                     │
│                                                             │
│  Position Concentration         Greeks Exposure              │
│  ┌────────────────────┐        ┌────────────────────┐      │
│  │ Top 5: 45%         │        │ Call:  +$45K      │      │
│  │ Top 10: 72%        │        │ Put:   -$12K      │      │
│  │ HHI Index: 0.28    │        │ Net:   +$33K      │      │
│  └────────────────────┘        └────────────────────┘      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Next Steps

- 📊 Learn about [Charting & Technical Analysis](#charting--analysis)
- 🔌 Explore the [API Reference](API_REFERENCE.md) for automation
- 🔧 Read the [Admin Guide](ADMIN_GUIDE.md) for system configuration
- 💻 Check out [Development](DEVELOPMENT.md) to extend DragonScope

---

<p align="center">
  Need help? Contact <a href="mailto:support@dragonscope.io">Enterprise Support</a>
</p>
