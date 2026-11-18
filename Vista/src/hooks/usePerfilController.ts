import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { extractErrorMessage, perfilApi } from '../lib/api'
import { useAuthStore } from '../store/authStore'
import { DEFAULT_GENERAL_BG, resolveMediaUrl, useAppearanceStore } from '../store/appearanceStore'

export function usePerfilController() {
  const { user, updateUser } = useAuthStore()
  const { fondoGeneralUrl } = useAppearanceStore()
  const resolvedGeneralBg = resolveMediaUrl(fondoGeneralUrl, DEFAULT_GENERAL_BG)
  const queryClient = useQueryClient()

  const [nombre, setNombre] = useState(user?.nombre ?? '')
  const [telefono, setTelefono] = useState('')
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [msg, setMsg] = useState('')
  const [pwdMsg, setPwdMsg] = useState('')

  const { data: perfil, isLoading } = useQuery({
    queryKey: ['perfil'],
    queryFn: perfilApi.get,
  })

  useEffect(() => {
    if (perfil) {
      setNombre(perfil.nombre)
      setTelefono(perfil.telefono ?? '')
    }
  }, [perfil])

  const { mutate: updatePerfil, isPending: updating } = useMutation({
    mutationFn: () => perfilApi.update({ nombre, telefono }),
    onSuccess: (data) => {
      updateUser({ nombre: data.nombre })
      setMsg('✅ Perfil actualizado exitosamente.')
      queryClient.invalidateQueries({ queryKey: ['perfil'] })
    },
    onError: (err: unknown) => setMsg('❌ ' + extractErrorMessage(err, 'Error al actualizar.')),
  })

  const { mutate: changePwd, isPending: changingPwd } = useMutation({
    mutationFn: () => perfilApi.changePassword(currentPassword, newPassword),
    onSuccess: () => {
      setPwdMsg('✅ Contraseña cambiada exitosamente.')
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
    },
    onError: (err: unknown) => setPwdMsg('❌ ' + extractErrorMessage(err, 'Error al cambiar contraseña.')),
  })

  const handlePwdSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setPwdMsg('')
    if (newPassword !== confirmPassword) {
      setPwdMsg('❌ Las contraseñas no coinciden.')
      return
    }
    changePwd()
  }

  return {
    user,
    perfil,
    isLoading,
    resolvedGeneralBg,
    nombre,
    setNombre,
    telefono,
    setTelefono,
    currentPassword,
    setCurrentPassword,
    newPassword,
    setNewPassword,
    confirmPassword,
    setConfirmPassword,
    msg,
    setMsg,
    pwdMsg,
    updating,
    changingPwd,
    updatePerfil,
    handlePwdSubmit,
  }
}
