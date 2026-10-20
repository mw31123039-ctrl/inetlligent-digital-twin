import type { Region } from '../types'

export const regions: Region[] = [
  { id: 'eyes', label: 'Eyes', description: 'Vision & eye comfort', symptomOptions: ['My eyes hurt', 'Dry or itchy eyes', 'Blurry vision'], locationQuestion: 'Is the pain in one eye or both?', locations: ['Left eye', 'Right eye', 'Both eyes'] },
  { id: 'head', label: 'Head', description: 'Head & facial area', symptomOptions: ['I have a headache', 'I feel dizzy', 'Pressure in my head'], locationQuestion: 'Where in your head do you notice it?', locations: ['Forehead', 'One side', 'All over'] },
  { id: 'chest', label: 'Chest', description: 'Chest & upper torso', symptomOptions: ['Chest discomfort', 'A tight feeling', 'Soreness when moving'], locationQuestion: 'Where in your chest do you notice it?', locations: ['Left side', 'Center', 'Right side'] },
  { id: 'abdomen', label: 'Abdomen', description: 'Stomach & lower torso', symptomOptions: ['My stomach hurts', 'I feel bloated', 'Abdominal cramps'], locationQuestion: 'Where in your abdomen do you notice it?', locations: ['Upper abdomen', 'Lower abdomen', 'All over'] },
  { id: 'arms', label: 'Arms', description: 'Shoulders to fingertips', symptomOptions: ['My arm hurts', 'Tingling in my hand', 'A stiff shoulder'], locationQuestion: 'Which arm is bothering you?', locations: ['Left arm', 'Right arm', 'Both arms'] },
  { id: 'legs', label: 'Legs', description: 'Hips to toes', symptomOptions: ['My leg hurts', 'A sore knee', 'Ankle discomfort'], locationQuestion: 'Which leg is bothering you?', locations: ['Left leg', 'Right leg', 'Both legs'] },
]
export const getRegion = (id: string) => regions.find(region => region.id === id)!
export const onsetOptions = ['Just today', 'A few days', 'A week or more']
export const characterOptions = ['Constant', 'Comes and goes', 'Only with movement']
