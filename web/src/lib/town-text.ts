/** Team text from src/views/evacuate.py, not challenge data: labelled as such wherever it shows. */

type CC = "BE" | "NL" | "DE"

/** Who does what, per country: team summary of the national crisis rules. (role, who, what to do) */
export const CHAIN: Record<CC, [string, string, string][]> = {
  BE: [
    ["Warns of the flood", "Wallonia's hydrological service (SPW) for rivers; the Royal Meteorological Institute for rain", "Flood and weather alerts to the governor and the mayors"],
    ["Orders the evacuation", "The mayor (municipal phase). The provincial governor takes over when several municipalities are hit; the Interior Minister, supported by the National Crisis Centre, in the federal phase", "Write down now who has the authority at each phase, and their deputy"],
    ["Alerts residents", "Mayor, governor or Interior Minister", "BE-Alert text and call, door-to-door for those not reached"],
    ["Opens the shelters", "Municipality, with its emergency planning officer", "Keys, staff, beds, food"],
  ],
  NL: [
    ["Warns of the flood", "Rijkswaterstaat for the Meuse; the water board for smaller rivers; KNMI for rain", "Warnings to the safety region and the mayors"],
    ["Orders the evacuation", "The mayor; the chair of the safety region when more than one municipality is hit", "Write down who decides and their deputy"],
    ["Alerts residents", "Safety region, for the mayor", "NL-Alert, sirens, door-to-door"],
    ["Opens the shelters", "Municipality, with the safety region", "Keys, staff, beds, food"],
  ],
  DE: [
    ["Warns of the flood", "The state flood service (Rhineland-Palatinate: LfU; North Rhine-Westphalia: LANUK and the district governments) for rivers; the German Weather Service for rain", "Warnings to the district and the municipalities"],
    ["Orders the evacuation", "The district (Kreis) or independent city as disaster-protection authority, led by the Landrat or mayor; the municipality for a local danger", "Write down who declares the disaster and orders the evacuation, and their deputy"],
    ["Alerts residents", "District and municipality", "Cell broadcast, NINA app, sirens, loudspeaker vans"],
    ["Opens the shelters", "Municipality, with the district", "Keys, staff, beds, food"],
  ],
}

export type Lang = "English" | "Français" | "Deutsch" | "Nederlands"
export const LOCAL_LANG: Record<CC, Lang> = { BE: "Français", NL: "Nederlands", DE: "Deutsch" }
const OR: Record<Lang, string> = { English: " or ", Français: " ou ", Deutsch: " oder ", Nederlands: " of " }

/** Draft evacuation message: team-written template (AI-assisted, ai_log.md 15); a native speaker checks it. */
const MSG: Record<Lang, string> = {
  English: "FLOOD WARNING – {town}. The river may flood the streets near it. Leave now. Take medicines, ID papers and a phone charger. Go to a shelter on higher ground: {near}. Cannot leave on your own? Call {line}. A bus will take you to {far}. Check on neighbours who are old, ill or alone. Never walk or drive through flood water.",
  Français: "ALERTE INONDATION – {town}. La rivière risque d'inonder les rues proches. Quittez votre domicile maintenant. Prenez vos médicaments, vos papiers d'identité et un chargeur de téléphone. Rendez-vous dans un centre d'accueil situé en hauteur : {near}. Vous ne pouvez pas partir par vos propres moyens ? Appelez le {line}. Un bus vous conduira à {far}. Prenez des nouvelles de vos voisins âgés, malades ou isolés. Ne traversez jamais une zone inondée, ni à pied ni en voiture.",
  Deutsch: "HOCHWASSERWARNUNG – {town}. Der Fluss kann die Straßen in seiner Nähe überfluten. Verlassen Sie jetzt Ihr Haus. Nehmen Sie Medikamente, Ausweis und Handy-Ladegerät mit. Gehen Sie zu einer höher gelegenen Notunterkunft: {near}. Können Sie nicht selbst gehen? Rufen Sie {line} an. Ein Bus bringt Sie zu {far}. Sehen Sie nach älteren, kranken oder alleinlebenden Nachbarn. Gehen oder fahren Sie niemals durch Hochwasser.",
  Nederlands: "WAARSCHUWING OVERSTROMING – {town}. De rivier kan de straten in de buurt overstromen. Vertrek nu. Neem medicijnen, uw identiteitsbewijs en een oplader mee. Ga naar een hoger gelegen opvanglocatie: {near}. Kunt u niet zelf weg? Bel {line}. Een bus brengt u naar {far}. Kijk om naar buren die oud, ziek of alleen zijn. Loop of rijd nooit door overstromingswater.",
}

export function message(lang: Lang, town: string, near: string[], far: string | null, line: string) {
  return MSG[lang]
    .replace("{town}", town)
    .replace("{near}", near.length ? near.join(OR[lang]) : "[shelter]")
    .replace("{far}", far ?? "[shelter]")
    .replace("{line}", line || "[help line]")
}

/** Before the season: the contingency steps 2021 showed missing. */
export const PREPARE = [
  "Confirm each shelter with its owner: keys, a 24/7 contact, beds, food, step-free access.",
  "Agree the buses with a transport operator, and where they pick people up.",
  "Keep a list of residents who cannot leave on their own (kept by the municipality, not in this tool).",
  "Name who orders the evacuation and a deputy, for every crisis phase.",
  "Run a drill: send the message, open one shelter, time it.",
]
