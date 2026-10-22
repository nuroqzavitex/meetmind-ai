import type { components } from "@/types/api";

type S = components["schemas"];

export type MeetingSummary = S["MeetingSummary"];
export type MeetingDetail = S["MeetingDetail"];
export type MeetingCreated = S["MeetingCreated"];
// Added to the OpenAPI schema by backend/scripts/export_openapi.py (form field, not a body model).
export type MeetingContextIn = S["MeetingContextIn"];
export type Participant = S["Participant"];
export type Utterance = S["Utterance"];
export type JobOut = S["JobOut"];
export type ItemOut = S["ItemOut"];
export type Hold = S["Hold"];
export type OverviewEntry = S["OverviewEntry"];
export type AgendaOut = S["AgendaOut"];
export type TasksOut = S["TasksOut"];
export type DecisionsOut = S["DecisionsOut"];
export type ItemAction = S["ItemAction"];
export type ItemPatch = S["ItemPatch"];
export type ItemEventOut = S["ItemEventOut"];
export type TopicOut = S["TopicOut"];
export type ApproveCleanOut = S["ApproveCleanOut"];
export type SpeakerOut = S["SpeakerOut"];
export type SpeakerAssignment = S["SpeakerAssignment"];
export type DiscordSettingsOut = S["DiscordSettingsOut"];
export type DiscordSettingsIn = S["DiscordSettingsIn"];
export type DiscordBotOut = S["DiscordBotOut"];
export type JoinCodeOut = S["JoinCodeOut"];
export type JoinRequestOut = S["JoinRequestOut"];

export type ItemType = ItemOut["type"];
export type ReviewState = NonNullable<ItemOut["review_state"]>;

export type QARequest = S["QARequest"];
export type QAResponse = S["QAResponse"];
export type Citation = S["Citation"];
