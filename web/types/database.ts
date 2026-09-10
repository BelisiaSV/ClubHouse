export type UserRole = "hoofdcoach" | "assistent_coach";
export type InvitationStatus = "pending" | "accepted" | "revoked";

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
          uploaded_by: string | null;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          title: string;
          description?: string | null;
          file_path: string;
          file_type: string;
          tags?: string[];
          uploaded_by: string;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          title?: string;
          description?: string | null;
          tags?: string[];
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
