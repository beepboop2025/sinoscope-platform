# DragonScope Enterprise - Development Guide

Guide for developers contributing to DragonScope Enterprise or building extensions.

---

## Table of Contents

1. [Development Environment Setup](#development-environment-setup)
2. [Code Structure](#code-structure)
3. [Adding New Services](#adding-new-services)
4. [Adding New Panels](#adding-new-panels)
5. [Testing Guidelines](#testing-guidelines)
6. [PR Checklist](#pr-checklist)

---

## Development Environment Setup

### Prerequisites

| Requirement | Version | Installation |
|-------------|---------|--------------|
| Node.js | 20.x LTS | [nodejs.org](https://nodejs.org) |
| Python | 3.11+ | [python.org](https://python.org) |
| Go | 1.21+ | [go.dev](https://go.dev) |
| Rust | 1.75+ | [rustup.rs](https://rustup.rs) |
| Docker | 24.x+ | [docker.com](https://docker.com) |
| PostgreSQL | 15+ | `brew install postgresql@15` |
| Redis | 7+ | `brew install redis` |

### Repository Structure

```
dragonscope-enterprise/
├── .github/                  # GitHub Actions, PR templates
├── api/                      # REST API definitions (OpenAPI)
├── backend/                  # Server-side code
│   ├── core/                 # Core business logic
│   ├── services/             # Microservices
│   ├── database/             # Migrations, models
│   └── websocket/            # Real-time communication
├── frontend/                 # Client-side code
│   ├── app/                  # Main application
│   ├── components/           # Reusable UI components
│   ├── panels/               # Trading panels
│   ├── charts/               # Charting library
│   └── themes/               # UI themes
├── shared/                   # Shared types, utilities
│   ├── types/                # TypeScript definitions
│   └── constants/            # Shared constants
├── docs/                     # Documentation
├── tests/                    # E2E and integration tests
├── scripts/                  # Development scripts
├── infrastructure/           # Terraform, K8s configs
└── tools/                    # Build tools, generators
```

### Initial Setup

```bash
# 1. Clone the repository
git clone https://github.com/dragonscope/enterprise.git
cd enterprise

# 2. Install dependencies
npm install              # Frontend dependencies
pip install -r requirements.txt  # Python dependencies
go mod download          # Go dependencies
cargo fetch              # Rust dependencies

# 3. Setup environment
cp .env.example .env
# Edit .env with your configuration

# 4. Start development services
docker-compose -f docker-compose.dev.yml up -d

# 5. Run database migrations
npm run db:migrate

# 6. Seed development data
npm run db:seed

# 7. Start development servers
npm run dev              # Starts all services in watch mode
```

### Development Services

After running `npm run dev`, the following services start:

| Service | URL | Description |
|---------|-----|-------------|
| Web UI | http://localhost:3000 | React application |
| API Server | http://localhost:8080 | REST API |
| WebSocket | ws://localhost:8081 | Real-time data |
| Storybook | http://localhost:6006 | Component library |
| API Docs | http://localhost:8080/docs | Swagger UI |

### IDE Configuration

#### VS Code Extensions (Recommended)

```json
// .vscode/extensions.json
{
  "recommendations": [
    "dbaeumer.vscode-eslint",
    "esbenp.prettier-vscode",
    "bradlc.vscode-tailwindcss",
    "ms-python.python",
    "golang.go",
    "rust-lang.rust-analyzer",
    "redhat.vscode-yaml",
    "ms-vscode.vscode-typescript-next",
    "orta.vscode-jest",
    "github.copilot"
  ]
}
```

#### VS Code Settings

```json
// .vscode/settings.json
{
  "editor.formatOnSave": true,
  "editor.defaultFormatter": "esbenp.prettier-vscode",
  "editor.codeActionsOnSave": {
    "source.fixAll.eslint": true
  },
  "typescript.preferences.importModuleSpecifier": "relative",
  "python.formatting.provider": "black",
  "python.linting.enabled": true,
  "go.formatTool": "goimports",
  "rust-analyzer.cargo.features": "all"
}
```

---

## Code Structure

### Frontend Architecture

```
frontend/
├── src/
│   ├── app/                    # Next.js app directory
│   │   ├── (dashboard)/        # Dashboard layout group
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx
│   │   │   └── workspace/
│   │   ├── api/                # API routes
│   │   └── auth/               # Authentication pages
│   │
│   ├── components/
│   │   ├── ui/                 # Primitive UI components
│   │   │   ├── Button.tsx
│   │   │   ├── Input.tsx
│   │   │   └── DataTable.tsx
│   │   ├── composite/          # Composite components
│   │   │   ├── SymbolSearch.tsx
│   │   │   ├── OrderTicket.tsx
│   │   │   └── AlertManager.tsx
│   │   └── charts/             # Chart components
│   │       ├── CandlestickChart.tsx
│   │       ├── VolumeProfile.tsx
│   │       └── TechnicalIndicators/
│   │
│   ├── panels/                 # Trading panels
│   │   ├── PanelRegistry.ts
│   │   ├── QuotePanel/
│   │   ├── ChartPanel/
│   │   ├── OrderBookPanel/
│   │   ├── PortfolioPanel/
│   │   └── NewsPanel/
│   │
│   ├── hooks/                  # Custom React hooks
│   │   ├── useMarketData.ts
│   │   ├── useWebSocket.ts
│   │   ├── usePositions.ts
│   │   └── useAlerts.ts
│   │
│   ├── stores/                 # Zustand state stores
│   │   ├── workspaceStore.ts
│   │   ├── marketDataStore.ts
│   │   └── tradingStore.ts
│   │
│   ├── lib/                    # Utilities
│   │   ├── api.ts              # API client
│   │   ├── websocket.ts        # WebSocket manager
│   │   ├── formatters.ts       # Data formatters
│   │   └── validators.ts       # Input validation
│   │
│   ├── types/                  # TypeScript types
│   │   ├── market.ts
│   │   ├── trading.ts
│   │   └── api.ts
│   │
│   └── styles/                 # Global styles
│       ├── globals.css
│       └── themes/
│
├── tests/                      # Test files
├── public/                     # Static assets
└── package.json
```

### Backend Architecture

```
backend/
├── src/
│   ├── core/                   # Core domain logic
│   │   ├── entities/           # Domain entities
│   │   │   ├── Order.ts
│   │   │   ├── Position.ts
│   │   │   └── Instrument.ts
│   │   ├── services/           # Domain services
│   │   │   ├── OrderService.ts
│   │   │   ├── RiskService.ts
│   │   │   └── MarketDataService.ts
│   │   └── value-objects/      # Value objects
│   │       ├── Money.ts
│   │       ├── Price.ts
│   │       └── Quantity.ts
│   │
│   ├── api/                    # API layer
│   │   ├── rest/               # REST controllers
│   │   │   ├── orders/
│   │   │   ├── portfolio/
│   │   │   └── market/
│   │   ├── websocket/          # WebSocket handlers
│   │   │   ├── MarketDataStream.ts
│   │   │   └── OrderUpdatesStream.ts
│   │   └── middleware/         # Express middleware
│   │       ├── auth.ts
│   │       ├── rateLimit.ts
│   │       └── validation.ts
│   │
│   ├── infrastructure/         # Infrastructure layer
│   │   ├── database/           # Database repositories
│   │   │   ├── repositories/
│   │   │   └── migrations/
│   │   ├── cache/              # Cache implementations
│   │   ├── messaging/          # Message queue
│   │   └── external/           # External service clients
│   │       ├── brokers/
│   │       ├── market-data/
│   │       └── news/
│   │
│   └── config/                 # Configuration
│       ├── database.ts
│       ├── redis.ts
│       └── kafka.ts
│
├── tests/                      # Backend tests
└── package.json
```

### Key Design Patterns

#### Frontend Patterns

**1. Container/Presentation Pattern**
```typescript
// Container (Smart Component)
// panels/ChartPanel/ChartPanel.container.tsx
export const ChartPanelContainer = () => {
  const { symbol } = usePanelParams();
  const { data, loading } = useMarketData(symbol);
  const { indicators, addIndicator } = useIndicators();
  
  return (
    <ChartPanel
      data={data}
      loading={loading}
      indicators={indicators}
      onAddIndicator={addIndicator}
    />
  );
};

// Presentation (Dumb Component)
// panels/ChartPanel/ChartPanel.tsx
export const ChartPanel = ({ data, loading, indicators, onAddIndicator }) => {
  return (
    <Panel>
      <Chart data={data} loading={loading} />
      <IndicatorList indicators={indicators} />
      <AddIndicatorButton onClick={onAddIndicator} />
    </Panel>
  );
};
```

**2. Custom Hooks for Data Fetching**
```typescript
// hooks/useMarketData.ts
export const useMarketData = (symbol: string) => {
  const [data, setData] = useState<MarketData | null>(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    const unsubscribe = marketDataService.subscribe(symbol, (update) => {
      setData(update);
      setLoading(false);
    });
    
    return unsubscribe;
  }, [symbol]);
  
  return { data, loading };
};
```

**3. State Management with Zustand**
```typescript
// stores/workspaceStore.ts
import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';

interface WorkspaceState {
  panels: Panel[];
  layout: Layout;
  activeSymbol: string;
  addPanel: (panel: Panel) => void;
  removePanel: (id: string) => void;
  updateLayout: (layout: Layout) => void;
  setActiveSymbol: (symbol: string) => void;
}

export const useWorkspaceStore = create<WorkspaceState>()(
  immer((set) => ({
    panels: [],
    layout: defaultLayout,
    activeSymbol: '',
    
    addPanel: (panel) =>
      set((state) => {
        state.panels.push(panel);
      }),
      
    removePanel: (id) =>
      set((state) => {
        state.panels = state.panels.filter((p) => p.id !== id);
      }),
      
    updateLayout: (layout) =>
      set((state) => {
        state.layout = layout;
      }),
      
    setActiveSymbol: (symbol) =>
      set((state) => {
        state.activeSymbol = symbol;
      }),
  }))
);
```

#### Backend Patterns

**1. Repository Pattern**
```typescript
// interfaces/IOrderRepository.ts
export interface IOrderRepository {
  findById(id: string): Promise<Order | null>;
  findByUser(userId: string): Promise<Order[]>;
  save(order: Order): Promise<Order>;
  update(order: Order): Promise<Order>;
  delete(id: string): Promise<void>;
}

// implementations/PostgresOrderRepository.ts
export class PostgresOrderRepository implements IOrderRepository {
  constructor(private db: Knex) {}
  
  async findById(id: string): Promise<Order | null> {
    const row = await this.db('orders').where({ id }).first();
    return row ? this.toEntity(row) : null;
  }
  
  // ... other methods
}
```

**2. Dependency Injection**
```typescript
// Container setup
container.register<IOrderRepository>('OrderRepository', {
  useClass: PostgresOrderRepository,
});

container.register<IOrderService>('OrderService', {
  useClass: OrderService,
});

// Usage in controller
@injectable()
export class OrderController {
  constructor(
    @inject('OrderService') private orderService: IOrderService
  ) {}
  
  async createOrder(req: Request, res: Response) {
    const order = await this.orderService.create(req.body);
    res.json(order);
  }
}
```

---

## Adding New Services

### Service Template

To create a new microservice, use the code generator:

```bash
npm run generate:service -- --name=analytics-service
```

This creates:

```
services/analytics-service/
├── src/
│   ├── index.ts
│   ├── config.ts
│   ├── handlers/
│   ├── models/
│   └── routes.ts
├── tests/
├── Dockerfile
├── package.json
└── README.md
```

### Service Implementation Example

```typescript
// services/analytics-service/src/index.ts
import { ServiceBootstrapper } from '@dragonscope/core';
import { AnalyticsConfig } from './config';
import { ReportHandler } from './handlers/ReportHandler';
import { routes } from './routes';

const bootstrapper = new ServiceBootstrapper({
  name: 'analytics-service',
  version: '1.0.0',
  config: AnalyticsConfig,
  routes,
  handlers: [ReportHandler],
  healthChecks: {
    database: () => checkDatabaseConnection(),
    cache: () => checkCacheConnection(),
  },
});

bootstrapper.start();
```

### Adding Service to Docker Compose

```yaml
# docker-compose.yml
services:
  analytics-service:
    build:
      context: ./services/analytics-service
      dockerfile: Dockerfile
    environment:
      - SERVICE_PORT=8084
      - DATABASE_URL=${ANALYTICS_DB_URL}
    depends_on:
      - postgres
      - kafka
    networks:
      - dragonscope
```

### Service Registration

```typescript
// backend/src/config/services.ts
export const services = {
  marketData: {
    url: process.env.MARKET_DATA_SERVICE_URL || 'http://market-data:8082',
    timeout: 5000,
  },
  orderExecution: {
    url: process.env.ORDER_SERVICE_URL || 'http://order-service:8083',
    timeout: 10000,
  },
  analytics: {
    url: process.env.ANALYTICS_SERVICE_URL || 'http://analytics-service:8084',
    timeout: 30000,
  },
};
```

---

## Adding New Panels

### Panel Architecture

```
panels/
├── PanelRegistry.ts          # Panel registration
├── PanelTypes.ts             # Panel type definitions
├── BasePanel/                # Base panel component
│   ├── BasePanel.tsx
│   ├── BasePanel.types.ts
│   └── BasePanel.styles.ts
└── [YourPanel]/
    ├── index.ts              # Public exports
    ├── YourPanel.tsx         # Main component
    ├── YourPanel.types.ts    # Type definitions
    ├── YourPanel.container.ts # Data container
    ├── YourPanel.config.ts   # Panel configuration
    ├── components/           # Sub-components
    ├── hooks/                # Panel-specific hooks
    └── utils/                # Utilities
```

### Creating a New Panel

**Step 1: Generate Panel Skeleton**

```bash
npm run generate:panel -- --name=earnings-calendar
```

**Step 2: Define Panel Configuration**

```typescript
// panels/EarningsCalendar/EarningsCalendar.config.ts
import { PanelConfig } from '../PanelTypes';

export const EarningsCalendarConfig: PanelConfig = {
  id: 'earnings-calendar',
  name: 'Earnings Calendar',
  description: 'Track upcoming earnings releases',
  icon: 'CalendarIcon',
  category: 'research',
  
  // Default dimensions
  defaultSize: {
    width: 400,
    height: 600,
  },
  
  // Minimum dimensions
  minSize: {
    width: 300,
    height: 400,
  },
  
  // Supported features
  features: {
    searchable: true,
    exportable: true,
    refreshable: true,
    customizable: true,
  },
  
  // Default settings
  defaultSettings: {
    lookAheadDays: 7,
    showSurprises: true,
    filterBySector: [],
    sortBy: 'date',
  },
  
  // Settings schema for UI
  settingsSchema: [
    {
      key: 'lookAheadDays',
      type: 'number',
      label: 'Look Ahead Days',
      min: 1,
      max: 30,
    },
    {
      key: 'showSurprises',
      type: 'boolean',
      label: 'Show EPS Surprises',
    },
    {
      key: 'filterBySector',
      type: 'multiSelect',
      label: 'Filter by Sector',
      options: [
        { value: 'technology', label: 'Technology' },
        { value: 'healthcare', label: 'Healthcare' },
        // ...
      ],
    },
  ],
};
```

**Step 3: Implement Panel Component**

```typescript
// panels/EarningsCalendar/EarningsCalendar.tsx
import React from 'react';
import { BasePanel } from '../BasePanel';
import { useEarningsCalendar } from './hooks/useEarningsCalendar';
import { EarningsList } from './components/EarningsList';
import { EarningsFilters } from './components/EarningsFilters';
import { EarningsCalendarProps } from './EarningsCalendar.types';

export const EarningsCalendar: React.FC<EarningsCalendarProps> = ({
  panelId,
  settings,
  onSettingsChange,
}) => {
  const { data, loading, error, refresh } = useEarningsCalendar(settings);
  
  return (
    <BasePanel
      panelId={panelId}
      title="Earnings Calendar"
      loading={loading}
      error={error}
      onRefresh={refresh}
      settings={settings}
      onSettingsChange={onSettingsChange}
      config={EarningsCalendarConfig}
    >
      <EarningsFilters
        settings={settings}
        onChange={onSettingsChange}
      />
      <EarningsList
        earnings={data}
        showSurprises={settings.showSurprises}
      />
    </BasePanel>
  );
};
```

**Step 4: Create Custom Hook**

```typescript
// panels/EarningsCalendar/hooks/useEarningsCalendar.ts
import { useState, useEffect } from 'react';
import { earningsApi } from '@/lib/api/earnings';
import { EarningsCalendarSettings } from '../EarningsCalendar.types';

export const useEarningsCalendar = (settings: EarningsCalendarSettings) => {
  const [data, setData] = useState<EarningsEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  
  const fetchData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await earningsApi.getCalendar({
        days: settings.lookAheadDays,
        sectors: settings.filterBySector,
      });
      setData(response.data);
    } catch (err) {
      setError(err as Error);
    } finally {
      setLoading(false);
    }
  };
  
  useEffect(() => {
    fetchData();
  }, [settings.lookAheadDays, settings.filterBySector.join(',')]);
  
  return {
    data,
    loading,
    error,
    refresh: fetchData,
  };
};
```

**Step 5: Register Panel**

```typescript
// panels/PanelRegistry.ts
import { EarningsCalendar } from './EarningsCalendar';
import { EarningsCalendarConfig } from './EarningsCalendar/EarningsCalendar.config';

export const panelRegistry = {
  // ... existing panels
  'earnings-calendar': {
    component: EarningsCalendar,
    config: EarningsCalendarConfig,
  },
};

// Type definition for panel IDs
export type PanelId = keyof typeof panelRegistry;
```

**Step 6: Add Panel to Menu**

```typescript
// components/PanelMenu/PanelMenu.tsx
const panelMenuItems = [
  {
    category: 'Market Data',
    items: [
      { id: 'quote', label: 'Quote', icon: 'QuoteIcon' },
      { id: 'chart', label: 'Chart', icon: 'ChartIcon' },
      { id: 'order-book', label: 'Order Book', icon: 'OrderBookIcon' },
    ],
  },
  {
    category: 'Research',
    items: [
      { id: 'news', label: 'News', icon: 'NewsIcon' },
      { id: 'earnings-calendar', label: 'Earnings Calendar', icon: 'CalendarIcon' },
      { id: 'sec-filings', label: 'SEC Filings', icon: 'DocumentIcon' },
    ],
  },
  // ...
];
```

---

## Testing Guidelines

### Testing Pyramid

```
        /\
       /  \
      / E2E\           (Few)  Cypress/Playwright
     /______\
    /        \
   /Integration\      (Some)  React Testing Library + MSW
  /____________\
 /              \
/    Unit Tests  \   (Many)  Jest/Vitest
/________________\
```

### Unit Testing

```typescript
// panels/EarningsCalendar/__tests__/EarningsCalendar.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { EarningsCalendar } from '../EarningsCalendar';
import { vi } from 'vitest';

// Mock the hook
vi.mock('../hooks/useEarningsCalendar', () => ({
  useEarningsCalendar: vi.fn(),
}));

describe('EarningsCalendar', () => {
  it('renders loading state', () => {
    (useEarningsCalendar as jest.Mock).mockReturnValue({
      data: [],
      loading: true,
      error: null,
    });
    
    render(<EarningsCalendar panelId="test" settings={defaultSettings} />);
    
    expect(screen.getByTestId('panel-loading')).toBeInTheDocument();
  });
  
  it('renders earnings events', () => {
    const mockData = [
      { symbol: 'AAPL', date: '2026-01-25', epsEstimate: 2.10 },
      { symbol: 'MSFT', date: '2026-01-26', epsEstimate: 3.20 },
    ];
    
    (useEarningsCalendar as jest.Mock).mockReturnValue({
      data: mockData,
      loading: false,
      error: null,
    });
    
    render(<EarningsCalendar panelId="test" settings={defaultSettings} />);
    
    expect(screen.getByText('AAPL')).toBeInTheDocument();
    expect(screen.getByText('MSFT')).toBeInTheDocument();
  });
  
  it('calls onSettingsChange when filters change', () => {
    const mockOnChange = vi.fn();
    
    (useEarningsCalendar as jest.Mock).mockReturnValue({
      data: [],
      loading: false,
      error: null,
    });
    
    render(
      <EarningsCalendar
        panelId="test"
        settings={defaultSettings}
        onSettingsChange={mockOnChange}
      />
    );
    
    fireEvent.click(screen.getByLabelText('Show EPS Surprises'));
    
    expect(mockOnChange).toHaveBeenCalledWith({
      ...defaultSettings,
      showSurprises: false,
    });
  });
});
```

### Integration Testing

```typescript
// tests/integration/earnings-api.test.ts
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';
import { earningsApi } from '@/lib/api/earnings';

const server = setupServer(
  http.get('/api/earnings/calendar', () => {
    return HttpResponse.json({
      data: [
        { symbol: 'AAPL', date: '2026-01-25', epsEstimate: 2.10 },
      ],
    });
  })
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('Earnings API', () => {
  it('fetches earnings calendar', async () => {
    const result = await earningsApi.getCalendar({ days: 7 });
    
    expect(result.data).toHaveLength(1);
    expect(result.data[0].symbol).toBe('AAPL');
  });
  
  it('handles errors', async () => {
    server.use(
      http.get('/api/earnings/calendar', () => {
        return new HttpResponse(null, { status: 500 });
      })
    );
    
    await expect(earningsApi.getCalendar({ days: 7 }))
      .rejects.toThrow('Failed to fetch earnings calendar');
  });
});
```

### E2E Testing

```typescript
// tests/e2e/panels/earnings-calendar.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Earnings Calendar Panel', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/workspace');
    await page.click('[data-testid="add-panel-button"]');
    await page.click('[data-testid="panel-earnings-calendar"]');
  });
  
  test('displays earnings events', async ({ page }) => {
    await expect(page.locator('[data-testid="earnings-list"]')).toBeVisible();
    await expect(page.locator('[data-testid="earnings-item"]')).toHaveCount.greaterThan(0);
  });
  
  test('filters by sector', async ({ page }) => {
    await page.click('[data-testid="sector-filter"]');
    await page.click('[data-testid="sector-technology"]');
    
    const items = await page.locator('[data-testid="earnings-item"]').count();
    expect(items).toBeGreaterThan(0);
    
    // Verify all items are technology sector
    const sectors = await page.locator('[data-testid="earnings-sector"]').allTextContents();
    expect(sectors.every(s => s === 'Technology')).toBe(true);
  });
  
  test('persists settings', async ({ page, context }) => {
    // Change settings
    await page.fill('[data-testid="look-ahead-input"]', '14');
    
    // Reload page
    await page.reload();
    
    // Verify settings persisted
    await expect(page.locator('[data-testid="look-ahead-input"]')).toHaveValue('14');
  });
});
```

### Running Tests

```bash
# Run all tests
npm test

# Run with coverage
npm run test:coverage

# Run specific test file
npm test -- panels/EarningsCalendar

# Run E2E tests
npm run test:e2e

# Run E2E with UI
npm run test:e2e:ui

# Watch mode
npm run test:watch
```

---

## PR Checklist

Before submitting a pull request, ensure:

### Code Quality

- [ ] Code follows project style guidelines (run `npm run lint`)
- [ ] No TypeScript errors (`npm run typecheck`)
- [ ] All tests pass (`npm test`)
- [ ] New code has test coverage > 80%
- [ ] No console errors or warnings
- [ ] No TODO/FIXME comments without issue references

### Documentation

- [ ] JSDoc comments for public APIs
- [ ] README updated for new features
- [ ] API documentation updated (if applicable)
- [ ] CHANGELOG.md updated

### Performance

- [ ] No unnecessary re-renders (verified with React DevTools)
- [ ] Database queries optimized (added indexes if needed)
- [ ] No memory leaks (verified with heap snapshots)
- [ ] Bundle size impact assessed (`npm run analyze`)

### Security

- [ ] No hardcoded secrets
- [ ] Input validation implemented
- [ ] SQL injection prevention verified
- [ ] XSS prevention verified
- [ ] Rate limiting considered for new endpoints

### UX/UI

- [ ] Responsive design (tested at 1280x720 and up)
- [ ] Dark mode support
- [ ] Keyboard navigation works
- [ ] Screen reader compatible (ARIA labels)
- [ ] Loading states implemented
- [ ] Error states handled gracefully

### Review

- [ ] Self-review completed
- [ ] PR description explains changes
- [ ] Related issues linked
- [ ] Screenshots/GIFs included for UI changes

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] E2E tests added/updated
- [ ] Manual testing performed

## Screenshots (if applicable)

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Tests pass
- [ ] Documentation updated
```

---

## Development Commands Reference

| Command | Description |
|---------|-------------|
| `npm run dev` | Start all services in development mode |
| `npm run build` | Build production bundles |
| `npm run lint` | Run ESLint |
| `npm run lint:fix` | Fix ESLint errors |
| `npm run typecheck` | Run TypeScript compiler |
| `npm test` | Run all tests |
| `npm run test:watch` | Run tests in watch mode |
| `npm run test:coverage` | Run tests with coverage |
| `npm run test:e2e` | Run E2E tests |
| `npm run db:migrate` | Run database migrations |
| `npm run db:seed` | Seed development data |
| `npm run db:reset` | Reset database |
| `npm run generate:service` | Generate new service |
| `npm run generate:panel` | Generate new panel |
| `npm run generate:component` | Generate new component |
| `npm run storybook` | Start Storybook |
| `npm run analyze` | Analyze bundle size |

---

<p align="center">
  Development questions? Join our <a href="https://discord.gg/dragonscope-dev">Discord</a>
</p>
