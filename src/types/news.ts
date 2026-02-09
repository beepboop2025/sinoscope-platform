export interface NewsArticle {
  id: string;
  title: string;
  summary: string;
  source: string;
  url: string;
  image: string;
  time: number;
  category: string;
  related?: string;
  sentiment?: number;
}
