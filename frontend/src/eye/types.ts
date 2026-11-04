export type EyeLocale = 'en' | 'ar-IQ' | 'ckb'
export type Localized = Record<EyeLocale, string>
export type EyeSide = 'left' | 'right' | 'both' | 'unknown'
export type EyeView = 'external' | 'section' | 'transparent' | 'exploded' | 'posterior' | 'corneal-detail' | 'retinal-detail'
export type Finding = 'present' | 'absent' | 'unknown'
export interface EyeStructure { id: string; group: string; label: Localized; function: Localized; shape: string; position: number[]; scale: number[]; preferred_view: EyeView; source_ids: string[]; clinical_review_status: string }
export interface EyeQuestion { id: string; field: string; text: Localized; options: {value:string;label:Localized}[]; when: Record<string,unknown>|null; type: string }
export interface EyeTurn { question_id: string; value: string; text?: string }
export interface EyeSession {
 id: string; locale: EyeLocale; use: 'education'; anatomy_explored: string[]; model_side: 'left'|'right';
 reported: Record<string,string|number>; symptoms: Record<string,Finding>; turns: EyeTurn[];
 messages: {role:'user'|'assistant';text:string;kind?:'education';source_urls?:string[];topic_id?:string}[]; acknowledgements: string[];
 urgency: 'unknown'|'urgent'|'emergency'; rule_ids: string[]; red_flags: Record<string,Finding>;
 missing: string[]; unconfirmed_explanations: never[]; source_urls: string[]; rule_version: string; source_version: string;
 clinical_review_status: 'draft'; created_at: string;
 care_plan?: {version:string;clinical_review_status:string;level:string;route:string;doctor:{title:Localized;description:Localized};steps:{id:string;text:Localized}[];comfort_measures_included:boolean;source_urls:string[]};
 doctor_summary?: string;
 pain_estimate?: {version:string;clinical_review_status:string;status:string;suggested_score:number|null;range:number[]|null;band:string;based_on:{description:string;activity_impact:string};numeric_source:string;confirmed:boolean;source_urls:string[]};
}
