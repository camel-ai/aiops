import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/Login.vue'
import Workspace from '../views/Workspace.vue'
import ProjectList from '../views/project/ProjectList.vue'
import ProjectAdd from '../views/project/ProjectAdd.vue'
import DeployCloud from '../views/deploy/DeployCloud.vue'
import ChangeCloud from '../views/change/ChangeCloud.vue'
import Template from '../views/template/Template.vue'
import ApiKey from '../views/apikey/ApiKey.vue'

const routes = [
  {
    path: '/',
    name: 'Login',
    component: Login,
    meta: { requiresAuth: false }
  },
  {
    path: '/workspace',
    name: 'Workspace',
    component: Workspace,
    meta: { requiresAuth: true },
    children: [
      {
        path: 'project/list',
        name: 'ProjectList',
        component: ProjectList,
        meta: { requiresAuth: true }
      },
      {
        path: 'project/add',
        name: 'ProjectAdd',
        component: ProjectAdd,
        meta: { requiresAuth: true, isModal: true }
      },
      {
        path: 'deploy',
        name: 'DeployCloud',
        component: DeployCloud,
        meta: { requiresAuth: true }
      },
      {
        path: 'change',
        name: 'ChangeCloud',
        component: ChangeCloud,
        meta: { requiresAuth: true }
      },
      {
        path: 'template',
        name: 'Template',
        component: Template,
        meta: { requiresAuth: true, isModal: true }
      },
      {
        path: 'template/add',
        name: 'AddTemplate',
        component: () => import('../views/template/AddTemplate.vue'),
        meta: { requiresAuth: true, isTemplateChild: true }
      },
      {
        path: 'template/edit/:id',
        name: 'EditTemplate',
        component: () => import('../views/template/EditTemplate.vue'),
        meta: { requiresAuth: true, isTemplateChild: true }
      },
      {
        path: 'apikey',
        name: 'ApiKey',
        component: ApiKey,
        meta: { requiresAuth: true, isModal: true }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(process.env.BASE_URL),
  routes
})

// 导航守卫
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  
  if (to.meta.requiresAuth && !token) {
    // 需要认证但没有token，重定向到登录页
    next({ name: 'Login' })
  } else if (to.name === 'Login' && token) {
    // 已登录用户访问登录页，重定向到工作区
    next({ name: 'Workspace' })
  } else {
    next()
  }
})

export default router
