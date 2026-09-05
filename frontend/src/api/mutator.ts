import axios, { type AxiosError, type AxiosRequestConfig } from 'axios'
import { supabase } from '@/lib/supabase'

const axiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
})

axiosInstance.interceptors.request.use(async (config) => {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

axiosInstance.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    if (error.response?.status === 401) {
      await supabase.auth.signOut()
      window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)

export const customInstance = <T>(config: AxiosRequestConfig): Promise<T> => {
  return axiosInstance(config).then((response) => response.data)
}
