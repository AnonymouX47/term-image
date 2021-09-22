import express, { Express } from 'express'
import cors from 'cors'
import { authRouter } from './auth/auth'
import { config } from 'dotenv'
import cookieParser from 'cookie-parser'

const PORT:number = parseInt(process.env.PORT || "3000")
const application:Express = express()

const secrets = config()

// middlewares
application.use(express.json())
application.use(cors())
application.use(express.urlencoded({ extended: true }))
application.use(cookieParser())

// routers
application.use("/auth", authRouter)

application.listen(PORT, ():void => {
    console.log(`Check out -> ${PORT}`)
})