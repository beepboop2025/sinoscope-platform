import { getCollectorData } from '../CollectorClient';

interface HuggingFaceModel {
  id: string;
  name: string;
  pipeline: string;
  downloads: number;
  likes: number;
  tags: string[];
  lastModified: string;
  library: string;
  isPrivate?: boolean;
}

export async function fetchHuggingFaceModels(_search: string = 'finance'): Promise<HuggingFaceModel[] | null> {
  const collected = await getCollectorData('huggingface_models');
  if (collected && (collected as HuggingFaceModel[]).length > 0) return collected as HuggingFaceModel[];
  return null;
}

export async function fetchFinanceModels(): Promise<HuggingFaceModel[] | null> {
  return fetchHuggingFaceModels();
}
