import { Request, Response, Router } from "express";
import { config } from 'dotenv'
import axios, { AxiosResponse } from 'axios'
import { Octokit } from '@octokit/core'
import { User } from "./user.interface";

const secrets = config()
export const authRouter:Router = Router();

// constants
const GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize?client_id="

// secrets
const GITHUB_CLIENT_ID = process.env.GITHUB_CLIENT_ID
const GITHUB_CLIENT_SECRET = process.env.GITHUB_CLIENT_SECRET

authRouter.get("/login", (request:Request, response:Response):void => {
    response.redirect(GITHUB_AUTH_URL + GITHUB_CLIENT_ID)
})

authRouter.get("/github/callback", (request:Request, response:Response):void => {
    const requestToken = request.query.code
  
    axios({
        method: 'post',
        url: `https://github.com/login/oauth/access_token?client_id=${GITHUB_CLIENT_ID}&client_secret=${GITHUB_CLIENT_SECRET}&code=${requestToken}`,
        headers: {
            accept: 'application/json'
        }
    }).then((axiosResponse:AxiosResponse<any>):void => {
        response.cookie('githubToken', Buffer.from(axiosResponse.data.access_token, 'utf8').toString("base64"))
        response.redirect("/auth/success")
    }).catch((error:any):void => {
        response.status(401).send(error)
    })
})

authRouter.get("/success", (request:Request, response:Response):void => {
    response.send({result:"success"})
})

authRouter.get("/get/current/user", (request:Request, response:Response) => {
    const githubClient = new Octokit({auth:Buffer.from(request.cookies.githubToken, "base64").toString("utf8")})
    githubClient.request('GET /user').then((githubResponse:any):void => {
        const data = githubResponse.data
        response.send(data as User)
    }).catch((error):void => {
        response.status(401).send(error)
    })
    
})