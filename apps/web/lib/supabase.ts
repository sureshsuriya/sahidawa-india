import { createClient } from "@supabase/supabase-js";
import { getSupabaseUrl, getSupabaseAnonKey } from "./env";

const supabaseUrl = getSupabaseUrl();
const supabaseKey = getSupabaseAnonKey();

const isTest = typeof process !== "undefined" && process.env.NODE_ENV === "test";

export const supabase = createClient(supabaseUrl, supabaseKey, {
    auth: {
        autoRefreshToken: !isTest,
        persistSession: !isTest,
        detectSessionInUrl: !isTest,
    },
});
