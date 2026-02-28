export interface LayoutItem {
  i: string;
  x: number;
  y: number;
  w: number;
  h: number;
  minW?: number;
  minH?: number;
}

export interface Workspace {
  id: string;
  name: string;
  icon: string;
  panels: string[];
  layouts: {
    lg: LayoutItem[];
    md?: LayoutItem[];
  };
}

export interface PanelRegistryEntry {
  id: string;
  name: string;
  component: string;
  category: string;
}

export interface Command {
  id: string;
  label: string;
  shortcut?: string;
  category: string;
  action: string | (() => void);
  icon?: string;
}
