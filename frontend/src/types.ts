export type RegionId = 'eyes' | 'head' | 'chest' | 'abdomen' | 'arms' | 'legs'
export type ViewMode = '2d' | '3d'
export type Navigation = 'Overview' | 'Body explorer' | 'Assessments' | 'History' | 'Settings'
export interface Region { id: RegionId; label: string; description: string; symptomOptions: string[]; locationQuestion: string; locations: string[] }
export interface Message { id: string; role: 'assistant' | 'user'; text: string }
export interface Answers { symptom: string; location: string; onset: string; character: string }
export interface Assessment {
  id: string
  region: RegionId
  answers: Answers
  pain: number
  messages: Message[]
  createdAt: string
}
export interface DemoSettings { rememberHistory: boolean; reducedMotion: boolean; failNextResponse: boolean }
export interface SymptomService {
  respond(region: RegionId, step: number, answer: string): Promise<{ message: string; options: string[]; complete: boolean }>
}
