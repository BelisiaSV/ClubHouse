export type UserRole = "hoofdcoach" | "assistent_coach";
export type InvitationStatus = "pending" | "accepted" | "revoked";
export type ScheduleEntryType =
  | "les"
  | "training"
  | "stage"
  | "wedstrijd"
  | "topsport_verplichting"
  | "overig";
export type PermissionRequestType = "vroeger_vertrek" | "later_toekomen" | "afwezigheid" | "overig";
export type PermissionStatus = "in_afwachting" | "goedgekeurd" | "geweigerd";
export type AthleteMeetingType = "klassenraad" | "deliberatie";

export interface Database {
  public: {
    Tables: {
      profiles: {
        Row: {
          id: string;
          email: string;
          full_name: string;
          avatar_url: string | null;
          role: UserRole;
          created_at: string;
        };
        Insert: {
          id: string;
          email: string;
          full_name: string;
          avatar_url?: string | null;
          role?: UserRole;
          created_at?: string;
        };
        Update: {
          full_name?: string;
          avatar_url?: string | null;
          role?: UserRole;
        };
        Relationships: [];
      };
      invitations: {
        Row: {
          id: string;
          email: string;
          role: UserRole;
          status: InvitationStatus;
          invited_by: string;
          created_at: string;
          accepted_at: string | null;
        };
        Insert: {
          id?: string;
          email: string;
          role?: UserRole;
          status?: InvitationStatus;
          invited_by: string;
          created_at?: string;
          accepted_at?: string | null;
        };
        Update: {
          status?: InvitationStatus;
          accepted_at?: string | null;
        };
        Relationships: [];
      };
      documents: {
        Row: {
          id: string;
          title: string;
          description: string | null;
          file_path: string;
          file_type: string;
          tags: string[];
          content_text: string | null;
          uploaded_by: string | null;
          created_at: string;
          updated_at: string;
          search_vector: unknown;
        };
        Insert: {
          id?: string;
          title: string;
          description?: string | null;
          file_path: string;
          file_type: string;
          tags?: string[];
          content_text?: string | null;
          uploaded_by: string;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          title?: string;
          description?: string | null;
          tags?: string[];
          content_text?: string | null;
          updated_at?: string;
        };
        Relationships: [];
      };
      comments: {
        Row: {
          id: string;
          document_id: string;
          author_id: string | null;
          parent_comment_id: string | null;
          body: string;
          created_at: string;
        };
        Insert: {
          id?: string;
          document_id: string;
          author_id: string;
          parent_comment_id?: string | null;
          body: string;
          created_at?: string;
        };
        Update: {
          body?: string;
        };
        Relationships: [];
      };
      athletes: {
        Row: {
          id: string;
          full_name: string;
          date_of_birth: string | null;
          sport: string | null;
          class_group: string | null;
          external_club: string | null;
          contact_email: string | null;
          contact_phone: string | null;
          guardian_name: string | null;
          guardian_phone: string | null;
          guardian_email: string | null;
          meal_plan_opt_in: boolean;
          is_boarding_student: boolean;
          boarding_school_name: string | null;
          departure_time: string | null;
          departure_notes: string | null;
          medical_screening_done: boolean;
          medical_screening_date: string | null;
          medical_screening_notes: string | null;
          notes: string | null;
          is_active: boolean;
          created_by: string | null;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          full_name: string;
          date_of_birth?: string | null;
          sport?: string | null;
          class_group?: string | null;
          external_club?: string | null;
          contact_email?: string | null;
          contact_phone?: string | null;
          guardian_name?: string | null;
          guardian_phone?: string | null;
          guardian_email?: string | null;
          meal_plan_opt_in?: boolean;
          is_boarding_student?: boolean;
          boarding_school_name?: string | null;
          departure_time?: string | null;
          departure_notes?: string | null;
          medical_screening_done?: boolean;
          medical_screening_date?: string | null;
          medical_screening_notes?: string | null;
          notes?: string | null;
          is_active?: boolean;
          created_by?: string | null;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          full_name?: string;
          date_of_birth?: string | null;
          sport?: string | null;
          class_group?: string | null;
          external_club?: string | null;
          contact_email?: string | null;
          contact_phone?: string | null;
          guardian_name?: string | null;
          guardian_phone?: string | null;
          guardian_email?: string | null;
          meal_plan_opt_in?: boolean;
          is_boarding_student?: boolean;
          boarding_school_name?: string | null;
          departure_time?: string | null;
          departure_notes?: string | null;
          medical_screening_done?: boolean;
          medical_screening_date?: string | null;
          medical_screening_notes?: string | null;
          notes?: string | null;
          is_active?: boolean;
          updated_at?: string;
        };
        Relationships: [];
      };
      athlete_meetings: {
        Row: {
          id: string;
          athlete_id: string;
          meeting_type: AthleteMeetingType;
          meeting_date: string;
          preparation_notes: string | null;
          report_notes: string | null;
          report_document_id: string | null;
          created_by: string | null;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          athlete_id: string;
          meeting_type: AthleteMeetingType;
          meeting_date: string;
          preparation_notes?: string | null;
          report_notes?: string | null;
          report_document_id?: string | null;
          created_by?: string | null;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          meeting_type?: AthleteMeetingType;
          meeting_date?: string;
          preparation_notes?: string | null;
          report_notes?: string | null;
          report_document_id?: string | null;
          updated_at?: string;
        };
        Relationships: [];
      };
      athlete_custom_fields: {
        Row: {
          id: string;
          athlete_id: string;
          label: string;
          value: string | null;
          created_by: string | null;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          athlete_id: string;
          label: string;
          value?: string | null;
          created_by?: string | null;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          label?: string;
          value?: string | null;
          updated_at?: string;
        };
        Relationships: [];
      };
      schedules: {
        Row: {
          id: string;
          athlete_id: string;
          entry_type: ScheduleEntryType;
          title: string;
          day_of_week: number | null;
          specific_date: string | null;
          start_time: string | null;
          end_time: string | null;
          location: string | null;
          notes: string | null;
          created_by: string | null;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          athlete_id: string;
          entry_type?: ScheduleEntryType;
          title: string;
          day_of_week?: number | null;
          specific_date?: string | null;
          start_time?: string | null;
          end_time?: string | null;
          location?: string | null;
          notes?: string | null;
          created_by?: string | null;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          entry_type?: ScheduleEntryType;
          title?: string;
          day_of_week?: number | null;
          specific_date?: string | null;
          start_time?: string | null;
          end_time?: string | null;
          location?: string | null;
          notes?: string | null;
          updated_at?: string;
        };
        Relationships: [];
      };
      permissions: {
        Row: {
          id: string;
          athlete_id: string;
          request_type: PermissionRequestType;
          requested_date: string;
          start_time: string | null;
          end_time: string | null;
          reason: string | null;
          status: PermissionStatus;
          requested_by: string | null;
          decided_by: string | null;
          decided_at: string | null;
          decision_note: string | null;
          created_at: string;
        };
        Insert: {
          id?: string;
          athlete_id: string;
          request_type?: PermissionRequestType;
          requested_date: string;
          start_time?: string | null;
          end_time?: string | null;
          reason?: string | null;
          status?: PermissionStatus;
          requested_by?: string | null;
          decided_by?: string | null;
          decided_at?: string | null;
          decision_note?: string | null;
          created_at?: string;
        };
        Update: {
          status?: PermissionStatus;
          decided_by?: string | null;
          decided_at?: string | null;
          decision_note?: string | null;
        };
        Relationships: [];
      };
      meals: {
        Row: {
          id: string;
          athlete_id: string;
          meal_date: string;
          is_registered: boolean;
          note: string | null;
          registered_by: string | null;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          athlete_id: string;
          meal_date: string;
          is_registered?: boolean;
          note?: string | null;
          registered_by?: string | null;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          is_registered?: boolean;
          note?: string | null;
          updated_at?: string;
        };
        Relationships: [];
      };
      messages: {
        Row: {
          id: string;
          sender_id: string | null;
          body: string;
          created_at: string;
          edited_at: string | null;
        };
        Insert: {
          id?: string;
          sender_id: string;
          body: string;
          created_at?: string;
          edited_at?: string | null;
        };
        Update: {
          body?: string;
          edited_at?: string | null;
        };
        Relationships: [];
      };
    };
    Views: Record<string, never>;
    Functions: Record<string, never>;
  };
}
